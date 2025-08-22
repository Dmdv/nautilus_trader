// -------------------------------------------------------------------------------------------------
//  Copyright (C) 2015-2025 Nautech Systems Pty Ltd. All rights reserved.
//  https://nautechsystems.io
//
//  Licensed under the GNU Lesser General Public License Version 3.0 (the "License");
//  You may not use this file except in compliance with the License.
//  You may obtain a copy of the License at https://www.gnu.org/licenses/lgpl-3.0.en.html
//
//  Unless required by applicable law or agreed to in writing, software
//  distributed under the License is distributed on an "AS IS" BASIS,
//  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
//  See the License for the specific language governing permissions and
//  limitations under the License.
// -------------------------------------------------------------------------------------------------

//! 4OTC data client implementation for Nautilus Trader.

use std::{
    collections::HashMap,
    sync::{
        atomic::{AtomicBool, AtomicU64, Ordering},
        Arc,
    },
    time::Instant,
};

use ahash::AHashSet;
use anyhow::{anyhow, Result};
use async_nats::{Client, ConnectOptions, Message, ServerAddr, Subscriber};
use prost::Message;
use nautilus_common::messages::data::{
    SubscribeBookDeltas, SubscribeBookDepth10,
    SubscribeQuotes, SubscribeTrades, UnsubscribeBookDeltas, UnsubscribeBookDepth10,
    UnsubscribeQuotes, UnsubscribeTrades,
};
use nautilus_core::time::get_atomic_clock_realtime;
use nautilus_data::client::DataClient;
use nautilus_model::{
    data::Data,
    identifiers::{ClientId, InstrumentId, Venue},
};
use tokio::{
    sync::{mpsc, RwLock},
    task::JoinHandle,
    time::{sleep, timeout},
};
use tracing::{debug, error, info, warn};

use crate::{
    config::FourOtcDataClientConfig,
    convert::DataConverter,
    enums::{ConnectionState, SubscriptionState},
    proto::MarketDataMessage,
    types::ClientStats,
};

/// 4OTC data client that connects to NATS streams and converts messages to Nautilus data types
pub struct FourOtcDataClient {
    /// Client configuration
    config: FourOtcDataClientConfig,
    
    /// Data converter for message transformation
    converter: Arc<RwLock<DataConverter>>,
    
    /// NATS client connection
    nats_client: Option<Client>,
    
    /// Active NATS subscribers
    subscribers: HashMap<String, Subscriber>,
    
    /// Connection state
    connection_state: Arc<RwLock<ConnectionState>>,
    
    /// Subscription states by subject pattern
    subscription_states: Arc<RwLock<HashMap<String, SubscriptionState>>>,
    
    /// Active subscriptions by instrument
    active_subscriptions: Arc<RwLock<HashMap<InstrumentId, AHashSet<String>>>>,
    
    /// Client statistics
    stats: Arc<RwLock<ClientStats>>,
    
    /// Message processing task handle
    message_task: Option<JoinHandle<()>>,
    
    /// Heartbeat task handle
    heartbeat_task: Option<JoinHandle<()>>,
    
    /// Shutdown signal
    shutdown_signal: Arc<AtomicBool>,
    
    /// Message counter for debugging
    message_counter: Arc<AtomicU64>,
    
    /// Data output channel
    data_tx: Option<mpsc::UnboundedSender<Data>>,
    
    /// Start time for uptime calculation
    start_time: Option<Instant>,
}

impl FourOtcDataClient {
    /// Creates a new 4OTC data client
    pub fn new(config: FourOtcDataClientConfig) -> Result<Self> {
        config.validate()?;
        
        let converter = Arc::new(RwLock::new(DataConverter::new(config.venue)));
        
        Ok(Self {
            config,
            converter,
            nats_client: None,
            subscribers: HashMap::new(),
            connection_state: Arc::new(RwLock::new(ConnectionState::Disconnected)),
            subscription_states: Arc::new(RwLock::new(HashMap::new())),
            active_subscriptions: Arc::new(RwLock::new(HashMap::new())),
            stats: Arc::new(RwLock::new(ClientStats::default())),
            message_task: None,
            heartbeat_task: None,
            shutdown_signal: Arc::new(AtomicBool::new(false)),
            message_counter: Arc::new(AtomicU64::new(0)),
            data_tx: None,
            start_time: None,
        })
    }
    
    /// Sets the data output channel
    pub fn set_data_channel(&mut self, tx: mpsc::UnboundedSender<Data>) {
        self.data_tx = Some(tx);
    }
    
    /// Gets current client statistics
    pub async fn get_stats(&self) -> ClientStats {
        self.stats.read().await.clone()
    }
    
    /// Gets current connection state
    pub async fn get_connection_state(&self) -> ConnectionState {
        *self.connection_state.read().await
    }
    
    /// Gets subscription state for a subject pattern
    pub async fn get_subscription_state(&self, subject: &str) -> SubscriptionState {
        self.subscription_states
            .read()
            .await
            .get(subject)
            .copied()
            .unwrap_or(SubscriptionState::Unsubscribed)
    }
    
    /// Registers an instrument mapping
    pub async fn register_instrument(&self, security_id: u32, instrument_id: InstrumentId) {
        self.converter
            .write()
            .await
            .register_instrument(security_id, instrument_id);
    }
    
    /// Creates NATS connection
    async fn create_nats_connection(&self) -> Result<Client> {
        let servers: Vec<ServerAddr> = self
            .config
            .nats
            .servers
            .iter()
            .map(|s| s.parse())
            .collect::<Result<Vec<_>, _>>()
            .map_err(|e| anyhow!("Failed to parse NATS servers: {}", e))?;
        
        let connect_options = ConnectOptions::new()
            .name(&self.config.nats.client_name)
            .connection_timeout(self.config.connection_timeout());
        
        info!("Connecting to NATS servers: {:?}", servers);
        
        let client = timeout(
            self.config.connection_timeout(),
            async_nats::connect_with_options(servers, connect_options),
        )
        .await
        .map_err(|_| anyhow!("NATS connection timeout"))?
        .map_err(|e| anyhow!("NATS connection failed: {}", e))?;
        
        info!("Successfully connected to NATS");
        Ok(client)
    }
    
    /// Starts the message processing task
    async fn start_message_processing(&mut self) -> Result<()> {
        if self.data_tx.is_none() {
            return Err(anyhow!("Data channel not set"));
        }
        
        let data_tx = self.data_tx.as_ref().unwrap().clone();
        let converter = Arc::clone(&self.converter);
        let stats = Arc::clone(&self.stats);
        let shutdown_signal = Arc::clone(&self.shutdown_signal);
        let message_counter = Arc::clone(&self.message_counter);
        let debug_mode = self.config.debug_mode;
        
        // Create message processing channel
        let (msg_tx, mut msg_rx) = mpsc::unbounded_channel::<Message>();
        
        // Store the sender for subscribers to use
        self.message_task = Some(tokio::spawn(async move {
            info!("Started message processing task");
            
            while let Some(message) = msg_rx.recv().await {
                if shutdown_signal.load(Ordering::Relaxed) {
                    break;
                }
                
                let count = message_counter.fetch_add(1, Ordering::Relaxed) + 1;
                
                if debug_mode && count % 1000 == 0 {
                    debug!("Processed {} messages", count);
                }
                
                // Update stats
                {
                    let mut stats_guard = stats.write().await;
                    stats_guard.increment_received();
                    stats_guard.update_last_message_time(get_atomic_clock_realtime().get_time_ns().as_u64());
                }
                
                // Process the message
                if let Err(e) = Self::process_nats_message(&message, &converter, &data_tx, &stats).await {
                    error!("Failed to process message: {}", e);
                    stats.write().await.increment_processing_error();
                }
            }
            
            info!("Message processing task stopped");
        }));
        
        Ok(())
    }
    
    /// Processes a NATS message
    async fn process_nats_message(
        message: &Message,
        converter: &Arc<RwLock<DataConverter>>,
        data_tx: &mpsc::UnboundedSender<Data>,
        stats: &Arc<RwLock<ClientStats>>,
    ) -> Result<()> {
        // Parse the protobuf message
        let market_data_message = Self::parse_message_payload(&message.payload).await?;
        
        // Convert to Nautilus data
        let converter_guard = converter.read().await;
        if let Some(data) = converter_guard.convert_message(&market_data_message)? {
            // Send to data engine
            if let Err(e) = data_tx.send(data) {
                error!("Failed to send data to engine: {}", e);
                return Err(anyhow!("Data channel send failed"));
            }
            
            stats.write().await.increment_processed();
        }
        
        Ok(())
    }
    
    /// Parses protobuf message payload from NATS
    async fn parse_message_payload(payload: &[u8]) -> Result<MarketDataMessage> {
        MarketDataMessage::decode(payload)
            .map_err(|e| anyhow!("Failed to decode protobuf message: {}", e))
    }
    
    /// Starts heartbeat monitoring
    async fn start_heartbeat_monitoring(&mut self) {
        let stats = Arc::clone(&self.stats);
        let shutdown_signal = Arc::clone(&self.shutdown_signal);
        let interval = self.config.heartbeat_interval();
        let start_time = Instant::now();
        
        self.heartbeat_task = Some(tokio::spawn(async move {
            info!("Started heartbeat monitoring with interval: {:?}", interval);
            
            while !shutdown_signal.load(Ordering::Relaxed) {
                sleep(interval).await;
                
                let uptime_secs = start_time.elapsed().as_secs();
                stats.write().await.update_uptime(uptime_secs);
            }
            
            info!("Heartbeat monitoring stopped");
        }));
    }
    
    /// Subscribes to a NATS subject pattern
    async fn subscribe_to_subject(&mut self, subject: &str) -> Result<()> {
        if let Some(client) = &self.nats_client {
            info!("Subscribing to NATS subject: {}", subject);
            
            let subscriber = client
                .subscribe(subject.to_string())
                .await
                .map_err(|e| anyhow!("Failed to subscribe to {}: {}", subject, e))?;
            
            self.subscribers.insert(subject.to_string(), subscriber);
            
            self.subscription_states
                .write()
                .await
                .insert(subject.to_string(), SubscriptionState::Subscribed);
            
            info!("Successfully subscribed to: {}", subject);
            Ok(())
        } else {
            Err(anyhow!("NATS client not connected"))
        }
    }
    
    /// Unsubscribes from a NATS subject pattern
    async fn unsubscribe_from_subject(&mut self, subject: &str) -> Result<()> {
        if let Some(mut subscriber) = self.subscribers.remove(subject) {
            info!("Unsubscribing from NATS subject: {}", subject);
            
            subscriber
                .unsubscribe()
                .await
                .map_err(|e| anyhow!("Failed to unsubscribe from {}: {}", subject, e))?;
            
            self.subscription_states
                .write()
                .await
                .insert(subject.to_string(), SubscriptionState::Unsubscribed);
            
            info!("Successfully unsubscribed from: {}", subject);
        }
        
        Ok(())
    }
    
    /// Builds NATS subject pattern for instrument data
    fn build_subject_pattern(&self, instrument_id: &InstrumentId, data_type: &str) -> String {
        let symbol = instrument_id.symbol.as_str();
        format!("{}.{}.{}", self.config.nats.subject_prefix, data_type, symbol)
    }
    
    /// Builds NATS subject pattern for all instruments of a data type
    fn build_wildcard_subject_pattern(&self, data_type: &str) -> String {
        format!("{}.{}.>", self.config.nats.subject_prefix, data_type)
    }
}

#[async_trait::async_trait]
impl DataClient for FourOtcDataClient {
    fn client_id(&self) -> ClientId {
        self.config.client_id
    }
    
    fn venue(&self) -> Option<Venue> {
        Some(self.config.venue)
    }
    
    fn start(&mut self) -> anyhow::Result<()> {
        info!("Starting 4OTC data client");
        self.start_time = Some(Instant::now());
        Ok(())
    }
    
    fn stop(&mut self) -> anyhow::Result<()> {
        info!("Stopping 4OTC data client");
        self.shutdown_signal.store(true, Ordering::Relaxed);
        
        // Cancel tasks
        if let Some(handle) = self.message_task.take() {
            handle.abort();
        }
        if let Some(handle) = self.heartbeat_task.take() {
            handle.abort();
        }
        
        Ok(())
    }
    
    fn reset(&mut self) -> anyhow::Result<()> {
        info!("Resetting 4OTC data client");
        self.stop()?;
        
        // Reset state
        self.subscribers.clear();
        self.nats_client = None;
        
        // Reset runtime state
        tokio::task::block_in_place(|| {
            tokio::runtime::Handle::current().block_on(async {
                *self.connection_state.write().await = ConnectionState::Disconnected;
                self.subscription_states.write().await.clear();
                self.active_subscriptions.write().await.clear();
                *self.stats.write().await = ClientStats::default();
            })
        });
        
        self.shutdown_signal.store(false, Ordering::Relaxed);
        self.message_counter.store(0, Ordering::Relaxed);
        
        Ok(())
    }
    
    fn dispose(&mut self) -> anyhow::Result<()> {
        info!("Disposing 4OTC data client");
        self.reset()
    }
    
    async fn connect(&mut self) -> anyhow::Result<()> {
        info!("Connecting 4OTC data client to NATS");
        
        *self.connection_state.write().await = ConnectionState::Connecting;
        
        match self.create_nats_connection().await {
            Ok(client) => {
                self.nats_client = Some(client);
                *self.connection_state.write().await = ConnectionState::Connected;
                
                // Start background tasks
                self.start_message_processing().await?;
                self.start_heartbeat_monitoring().await;
                
                info!("4OTC data client connected successfully");
                Ok(())
            }
            Err(e) => {
                error!("Failed to connect 4OTC data client: {}", e);
                *self.connection_state.write().await = ConnectionState::Failed;
                self.stats.write().await.increment_connection_error();
                Err(e)
            }
        }
    }
    
    async fn disconnect(&mut self) -> anyhow::Result<()> {
        info!("Disconnecting 4OTC data client");
        
        // Unsubscribe from all subjects
        let subjects: Vec<String> = self.subscribers.keys().cloned().collect();
        for subject in subjects {
            if let Err(e) = self.unsubscribe_from_subject(&subject).await {
                warn!("Failed to unsubscribe from {}: {}", subject, e);
            }
        }
        
        self.stop()?;
        self.nats_client = None;
        *self.connection_state.write().await = ConnectionState::Disconnected;
        
        info!("4OTC data client disconnected");
        Ok(())
    }
    
    fn is_connected(&self) -> bool {
        tokio::task::block_in_place(|| {
            tokio::runtime::Handle::current().block_on(async {
                matches!(*self.connection_state.read().await, ConnectionState::Connected)
            })
        })
    }

    fn is_disconnected(&self) -> bool {
        !self.is_connected()
    }

    fn subscribe_book_deltas(&mut self, cmd: &SubscribeBookDeltas) -> anyhow::Result<()> {
        tokio::task::block_in_place(|| {
            tokio::runtime::Handle::current().block_on(async {
                self.subscribe_book_deltas_async(cmd.clone()).await
            })
        })
    }

    fn subscribe_book_depth10(&mut self, cmd: &SubscribeBookDepth10) -> anyhow::Result<()> {
        tokio::task::block_in_place(|| {
            tokio::runtime::Handle::current().block_on(async {
                self.subscribe_book_depth10_async(cmd.clone()).await
            })
        })
    }

    fn subscribe_quotes(&mut self, cmd: &SubscribeQuotes) -> anyhow::Result<()> {
        tokio::task::block_in_place(|| {
            tokio::runtime::Handle::current().block_on(async {
                self.subscribe_quotes_async(cmd.clone()).await
            })
        })
    }

    fn subscribe_trades(&mut self, cmd: &SubscribeTrades) -> anyhow::Result<()> {
        tokio::task::block_in_place(|| {
            tokio::runtime::Handle::current().block_on(async {
                self.subscribe_trades_async(cmd.clone()).await
            })
        })
    }
}

// Subscription method implementations
impl FourOtcDataClient {
    async fn subscribe_book_deltas_async(&mut self, cmd: SubscribeBookDeltas) -> anyhow::Result<()> {
        let subject = self.build_subject_pattern(&cmd.instrument_id, "snapshot.level2");
        self.subscribe_to_subject(&subject).await?;
        
        self.active_subscriptions
            .write()
            .await
            .entry(cmd.instrument_id)
            .or_default()
            .insert(subject);
        
        Ok(())
    }
    
    async fn unsubscribe_book_deltas(&mut self, cmd: UnsubscribeBookDeltas) -> anyhow::Result<()> {
        let subject = self.build_subject_pattern(&cmd.instrument_id, "snapshot.level2");
        self.unsubscribe_from_subject(&subject).await?;
        
        if let Some(subs) = self.active_subscriptions.write().await.get_mut(&cmd.instrument_id) {
            subs.remove(&subject);
        }
        
        Ok(())
    }
    
    async fn subscribe_book_depth10_async(&mut self, cmd: SubscribeBookDepth10) -> anyhow::Result<()> {
        let subject = self.build_subject_pattern(&cmd.instrument_id, "snapshot.level2");
        self.subscribe_to_subject(&subject).await?;
        
        self.active_subscriptions
            .write()
            .await
            .entry(cmd.instrument_id)
            .or_default()
            .insert(subject);
        
        Ok(())
    }
    
    async fn unsubscribe_book_depth10(&mut self, cmd: UnsubscribeBookDepth10) -> anyhow::Result<()> {
        let subject = self.build_subject_pattern(&cmd.instrument_id, "snapshot.level2");
        self.unsubscribe_from_subject(&subject).await?;
        
        if let Some(subs) = self.active_subscriptions.write().await.get_mut(&cmd.instrument_id) {
            subs.remove(&subject);
        }
        
        Ok(())
    }
    
    async fn subscribe_quotes_async(&mut self, cmd: SubscribeQuotes) -> anyhow::Result<()> {
        let subject = self.build_subject_pattern(&cmd.instrument_id, "snapshot.level2");
        self.subscribe_to_subject(&subject).await?;
        
        self.active_subscriptions
            .write()
            .await
            .entry(cmd.instrument_id)
            .or_default()
            .insert(subject);
        
        Ok(())
    }
    
    async fn unsubscribe_quotes(&mut self, cmd: UnsubscribeQuotes) -> anyhow::Result<()> {
        let subject = self.build_subject_pattern(&cmd.instrument_id, "snapshot.level2");
        self.unsubscribe_from_subject(&subject).await?;
        
        if let Some(subs) = self.active_subscriptions.write().await.get_mut(&cmd.instrument_id) {
            subs.remove(&subject);
        }
        
        Ok(())
    }
    
    async fn subscribe_trades_async(&mut self, cmd: SubscribeTrades) -> anyhow::Result<()> {
        let subject = self.build_subject_pattern(&cmd.instrument_id, "trades");
        self.subscribe_to_subject(&subject).await?;
        
        self.active_subscriptions
            .write()
            .await
            .entry(cmd.instrument_id)
            .or_default()
            .insert(subject);
        
        Ok(())
    }
    
    async fn unsubscribe_trades(&mut self, cmd: UnsubscribeTrades) -> anyhow::Result<()> {
        let subject = self.build_subject_pattern(&cmd.instrument_id, "trades");
        self.unsubscribe_from_subject(&subject).await?;
        
        if let Some(subs) = self.active_subscriptions.write().await.get_mut(&cmd.instrument_id) {
            subs.remove(&subject);
        }
        
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use nautilus_model::identifiers::Symbol;
    
    #[test]
    fn test_client_creation() {
        let config = FourOtcDataClientConfig::default();
        let client = FourOtcDataClient::new(config).unwrap();
        
        assert_eq!(client.client_id(), ClientId::from("FOUROTC-001"));
        assert_eq!(client.venue(), Some(Venue::from("4OTC")));
    }
    
    #[test]
    fn test_subject_pattern_building() {
        let config = FourOtcDataClientConfig::default();
        let client = FourOtcDataClient::new(config).unwrap();
        
        let instrument_id = InstrumentId::from("BTCUSD.4OTC");
        let subject = client.build_subject_pattern(&instrument_id, "trades");
        assert_eq!(subject, "market.4otc.trades.BTCUSD");
        
        let wildcard = client.build_wildcard_subject_pattern("snapshot.level2");
        assert_eq!(wildcard, "market.4otc.snapshot.level2.>");
    }
    
    #[tokio::test]
    async fn test_connection_state_transitions() {
        let config = FourOtcDataClientConfig::default();
        let client = FourOtcDataClient::new(config).unwrap();
        
        assert_eq!(client.get_connection_state().await, ConnectionState::Disconnected);
        
        // Note: Cannot test actual connection without running NATS server
        // This would test state management logic
    }
}