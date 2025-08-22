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

//! 4OTC data client binary for testing and standalone usage.

use std::{
    sync::{
        atomic::{AtomicBool, Ordering},
        Arc,
    },
    time::Duration,
};

use anyhow::Result;
use clap::Parser;
use fourotc::{
    client::FourOtcDataClient,
    config::{FourOtcDataClientConfig, NatsConfig},
};
use nautilus_common::messages::data::{SubscribeBookDepth10, SubscribeTrades};
use nautilus_data::client::DataClient;
use nautilus_model::{
    data::Data,
    enums::BookType,
    identifiers::{ClientId, InstrumentId, Venue},
};
use tokio::{
    signal,
    sync::mpsc,
    time::{interval, sleep},
};
use tracing::{error, info, warn};
use tracing_subscriber::{layer::SubscriberExt, util::SubscriberInitExt};

/// Command-line arguments for the 4OTC data client
#[derive(Parser, Debug)]
#[command(name = "fourotc-data-client")]
#[command(about = "4OTC data client for Nautilus Trader")]
struct Args {
    /// NATS server URL
    #[arg(short, long, default_value = "nats://localhost:4222")]
    nats_url: String,
    
    /// NATS subject prefix
    #[arg(short, long, default_value = "market.4otc")]
    subject_prefix: String,
    
    /// Client ID
    #[arg(short, long, default_value = "FOUROTC-001")]
    client_id: String,
    
    /// Venue name
    #[arg(short, long, default_value = "4OTC")]
    venue: String,
    
    /// Instruments to subscribe to (comma-separated)
    #[arg(short, long, default_value = "BTCUSD.4OTC,ETHUSD.4OTC")]
    instruments: String,
    
    /// Enable debug mode
    #[arg(short, long)]
    debug: bool,
    
    /// Subscribe to trades
    #[arg(long, default_value = "true")]
    subscribe_trades: bool,
    
    /// Subscribe to order book
    #[arg(long, default_value = "true")]
    subscribe_book: bool,
    
    /// Statistics reporting interval in seconds
    #[arg(long, default_value = "30")]
    stats_interval: u64,
}

#[tokio::main]
async fn main() -> Result<()> {
    let args = Args::parse();
    
    // Initialize tracing
    init_logging(args.debug)?;
    
    info!("Starting 4OTC data client");
    info!("Configuration: {:#?}", args);
    
    // Parse instruments
    let instruments: Vec<InstrumentId> = args
        .instruments
        .split(',')
        .map(|s| InstrumentId::from(s.trim()))
        .collect();
    
    info!("Instruments to subscribe: {:?}", instruments);
    
    // Create configuration
    let config = create_config(&args)?;
    
    // Create and start data client
    let mut client = FourOtcDataClient::new(config)?;
    
    // Set up data channel
    let (data_tx, mut data_rx) = mpsc::unbounded_channel::<Data>();
    client.set_data_channel(data_tx);
    
    // Register instruments (example mapping)
    for (i, instrument_id) in instruments.iter().enumerate() {
        let security_id = (i + 1) as u32 * 100; // Example mapping
        client.register_instrument(security_id, *instrument_id).await;
        info!("Registered instrument {} with security_id {}", instrument_id, security_id);
    }
    
    // Start client
    client.start()?;
    client.connect().await?;
    
    info!("Client connected, starting subscriptions");
    
    // Subscribe to data
    if let Err(e) = subscribe_to_data(&mut client, &instruments, &args).await {
        error!("Failed to subscribe to data: {}", e);
        return Err(e);
    }
    
    // Set up shutdown signal
    let shutdown = Arc::new(AtomicBool::new(false));
    let shutdown_clone = Arc::clone(&shutdown);
    
    tokio::spawn(async move {
        signal::ctrl_c().await.expect("Failed to listen for ctrl+c");
        info!("Shutdown signal received");
        shutdown_clone.store(true, Ordering::Relaxed);
    });
    
    // Set up statistics reporting
    let client_stats = Arc::new(tokio::sync::Mutex::new(client));
    let stats_client = Arc::clone(&client_stats);
    let stats_shutdown = Arc::clone(&shutdown);
    
    tokio::spawn(async move {
        let mut interval = interval(Duration::from_secs(args.stats_interval));
        
        while !stats_shutdown.load(Ordering::Relaxed) {
            interval.tick().await;
            
            let client = stats_client.lock().await;
            let stats = client.get_stats().await;
            let connection_state = client.get_connection_state().await;
            
            info!(
                "Stats - Messages: {} (processed: {}, errors: {}), Success rate: {:.2}%, Connection: {}",
                stats.messages_received,
                stats.messages_processed,
                stats.processing_errors,
                stats.success_rate() * 100.0,
                connection_state
            );
        }
    });
    
    // Main message processing loop
    info!("Starting main processing loop");
    let mut message_count = 0u64;
    
    while !shutdown.load(Ordering::Relaxed) {
        tokio::select! {
            Some(data) = data_rx.recv() => {
                message_count += 1;
                
                if args.debug || message_count % 100 == 0 {
                    info!("Received data #{}: {:?}", message_count, data.instrument_id());
                }
                
                // Process the data (in a real application, this would be sent to Nautilus)
                process_market_data(data, args.debug).await;
            }
            _ = sleep(Duration::from_millis(100)) => {
                // Periodic check for shutdown
                continue;
            }
        }
    }
    
    info!("Shutting down client");
    
    // Disconnect and clean up
    {
        let mut client = client_stats.lock().await;
        if let Err(e) = client.disconnect().await {
            warn!("Error during disconnect: {}", e);
        }
        client.dispose()?;
    }
    
    info!("4OTC data client stopped. Total messages processed: {}", message_count);
    Ok(())
}

/// Initialize logging based on debug flag
fn init_logging(debug: bool) -> Result<()> {
    let log_level = if debug {
        tracing::Level::DEBUG
    } else {
        tracing::Level::INFO
    };
    
    tracing_subscriber::registry()
        .with(
            tracing_subscriber::EnvFilter::try_from_default_env()
                .unwrap_or_else(|_| format!("fourotc={}", log_level).into()),
        )
        .with(tracing_subscriber::fmt::layer())
        .init();
    
    Ok(())
}

/// Create client configuration from command-line arguments
fn create_config(args: &Args) -> Result<FourOtcDataClientConfig> {
    let nats_config = NatsConfig {
        servers: vec![args.nats_url.clone()],
        subject_prefix: args.subject_prefix.clone(),
        client_name: format!("{}-client", args.client_id),
        connection_timeout_secs: 10,
        max_reconnect_attempts: Some(5),
        reconnect_delay_ms: 1000,
        enable_jetstream: false,
        jetstream_consumer: None,
    };
    
    let mut config = FourOtcDataClientConfig::new(
        ClientId::from(args.client_id.as_str()),
        Venue::from(args.venue.as_str()),
    );
    
    config.nats = nats_config;
    config.debug_mode = args.debug;
    config.buffer_size = 10000;
    config.heartbeat_interval_secs = 30;
    
    if args.debug {
        config.heartbeat_interval_secs = 10;
    }
    
    config.validate()?;
    Ok(config)
}

/// Subscribe to market data for instruments
async fn subscribe_to_data(
    client: &mut FourOtcDataClient,
    instruments: &[InstrumentId],
    args: &Args,
) -> Result<()> {
    for instrument_id in instruments {
        info!("Subscribing to data for {}", instrument_id);
        
        if args.subscribe_trades {
            let cmd = SubscribeTrades {
                instrument_id: *instrument_id,
                client_id: Some(client.client_id()),
                venue: Some(client.venue().unwrap()),
                command_id: uuid::Uuid::new_v4().into(),
                ts_init: nautilus_core::time::get_atomic_clock_realtime().get_time_ns(),
                params: None,
            };
            
            match client.subscribe_trades(&cmd) {
                Ok(_) => info!("Successfully subscribed to trades for {}", instrument_id),
                Err(e) => warn!("Failed to subscribe to trades for {}: {}", instrument_id, e),
            }
        }
        
        if args.subscribe_book {
            let cmd = SubscribeBookDepth10 {
                instrument_id: *instrument_id,
                book_type: BookType::L2_MBP,
                client_id: Some(client.client_id()),
                venue: Some(client.venue().unwrap()),
                command_id: uuid::Uuid::new_v4().into(),
                ts_init: nautilus_core::time::get_atomic_clock_realtime().get_time_ns(),
                depth: None,
                managed: false,
                params: None,
            };
            
            match client.subscribe_book_depth10(&cmd) {
                Ok(_) => info!("Successfully subscribed to book depth for {}", instrument_id),
                Err(e) => warn!("Failed to subscribe to book depth for {}: {}", instrument_id, e),
            }
        }
    }
    
    Ok(())
}

/// Process received market data
async fn process_market_data(data: Data, debug: bool) {
    match data {
        Data::Trade(trade) => {
            if debug {
                info!("Trade: {} {} @ {} ({})", 
                    trade.instrument_id, 
                    trade.size, 
                    trade.price,
                    trade.aggressor_side
                );
            }
        }
        Data::Depth10(depth) => {
            if debug {
                info!("Depth10: {} - Best bid: {} @ {}, Best ask: {} @ {}",
                    depth.instrument_id,
                    depth.bids[0].size,
                    depth.bids[0].price,
                    depth.asks[0].size,
                    depth.asks[0].price
                );
            }
        }
        Data::Quote(quote) => {
            if debug {
                info!("Quote: {} - Bid: {} @ {}, Ask: {} @ {}",
                    quote.instrument_id,
                    quote.bid_size,
                    quote.bid_price,
                    quote.ask_size,
                    quote.ask_price
                );
            }
        }
        _ => {
            if debug {
                info!("Received other data type: {:?}", data.instrument_id());
            }
        }
    }
}