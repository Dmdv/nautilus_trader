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

//! Configuration types for the 4OTC adapter.

use std::time::Duration;

use nautilus_model::identifiers::{ClientId, Venue};
use serde::{Deserialize, Serialize};

use crate::constants;

/// Configuration for NATS connection and subscription parameters.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct NatsConfig {
    /// NATS server URLs
    pub servers: Vec<String>,
    
    /// Subject prefix for subscribing to market data
    pub subject_prefix: String,
    
    /// Client name for NATS connection
    pub client_name: String,
    
    /// Connection timeout in seconds
    pub connection_timeout_secs: u64,
    
    /// Maximum reconnection attempts
    pub max_reconnect_attempts: Option<u32>,
    
    /// Reconnection delay in milliseconds
    pub reconnect_delay_ms: u64,
    
    /// Enable JetStream consumer
    pub enable_jetstream: bool,
    
    /// JetStream consumer configuration (if enabled)
    pub jetstream_consumer: Option<JetStreamConsumerConfig>,
}

impl Default for NatsConfig {
    fn default() -> Self {
        Self {
            servers: vec![constants::DEFAULT_NATS_URL.to_string()],
            subject_prefix: constants::DEFAULT_SUBJECT_PREFIX.to_string(),
            client_name: format!("{}-client", constants::DEFAULT_CLIENT_ID),
            connection_timeout_secs: 10,
            max_reconnect_attempts: Some(10),
            reconnect_delay_ms: 1000,
            enable_jetstream: false,
            jetstream_consumer: None,
        }
    }
}

/// JetStream consumer configuration
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct JetStreamConsumerConfig {
    /// Stream name to consume from
    pub stream_name: String,
    
    /// Consumer name (if not provided, will be auto-generated)
    pub consumer_name: Option<String>,
    
    /// Delivery policy
    pub deliver_policy: DeliverPolicy,
    
    /// Acknowledge policy
    pub ack_policy: AckPolicy,
    
    /// Maximum number of outstanding acknowledgments
    pub max_ack_pending: Option<i64>,
    
    /// Acknowledgment wait time in seconds
    pub ack_wait_secs: Option<u64>,
}

impl Default for JetStreamConsumerConfig {
    fn default() -> Self {
        Self {
            stream_name: "4OTC_MARKET_DATA".to_string(),
            consumer_name: None,
            deliver_policy: DeliverPolicy::New,
            ack_policy: AckPolicy::Explicit,
            max_ack_pending: Some(1000),
            ack_wait_secs: Some(30),
        }
    }
}

/// JetStream delivery policy
#[derive(Debug, Clone, Copy, Serialize, Deserialize)]
pub enum DeliverPolicy {
    /// Deliver new messages only
    New,
    /// Deliver all messages
    All,
    /// Deliver messages from a specific sequence
    BySequence(u64),
    /// Deliver messages from a specific time
    ByTime(u64),
    /// Deliver last message per subject
    LastPerSubject,
}

/// JetStream acknowledgment policy
#[derive(Debug, Clone, Copy, Serialize, Deserialize)]
pub enum AckPolicy {
    /// No acknowledgment required
    None,
    /// Acknowledgment required
    Explicit,
    /// All messages up to this one are acknowledged
    All,
}

/// Data format configuration
#[derive(Debug, Clone, Copy, Serialize, Deserialize)]
pub enum DataFormat {
    /// JSON format (legacy)
    Json,
    /// Protocol Buffers format (preferred)
    Protobuf,
}

impl Default for DataFormat {
    fn default() -> Self {
        Self::Json
    }
}

/// Subscription configuration for specific data types
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SubscriptionConfig {
    /// Subscribe to order book snapshots
    pub order_book_snapshots: bool,
    
    /// Subscribe to order book updates/deltas
    pub order_book_updates: bool,
    
    /// Subscribe to trades
    pub trades: bool,
    
    /// Subscribe to security definitions
    pub security_definitions: bool,
    
    /// Subscribe to security status updates
    pub security_status: bool,
    
    /// Subscribe to heartbeats
    pub heartbeats: bool,
    
    /// Maximum order book depth (if supported)
    pub max_depth: Option<u32>,
    
    /// Specific venue IDs to subscribe to (None = all venues)
    pub venue_ids: Option<Vec<u32>>,
    
    /// Specific security IDs to subscribe to (None = all securities)
    pub security_ids: Option<Vec<u32>>,
}

impl Default for SubscriptionConfig {
    fn default() -> Self {
        Self {
            order_book_snapshots: true,
            order_book_updates: true,
            trades: true,
            security_definitions: true,
            security_status: true,
            heartbeats: false,
            max_depth: Some(10),
            venue_ids: None,
            security_ids: None,
        }
    }
}

/// Main configuration for the 4OTC data client
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct FourOtcDataClientConfig {
    /// Client identifier for this data client instance
    pub client_id: ClientId,
    
    /// Venue identifier
    pub venue: Venue,
    
    /// NATS connection configuration
    pub nats: NatsConfig,
    
    /// Data format for message parsing
    pub data_format: DataFormat,
    
    /// Subscription configuration
    pub subscriptions: SubscriptionConfig,
    
    /// Buffer size for internal message queues
    pub buffer_size: usize,
    
    /// Heartbeat interval for health monitoring (seconds)
    pub heartbeat_interval_secs: u64,
    
    /// Enable message filtering for better performance
    pub enable_message_filtering: bool,
    
    /// Debug mode for additional logging
    pub debug_mode: bool,
}

impl Default for FourOtcDataClientConfig {
    fn default() -> Self {
        Self {
            client_id: ClientId::from(constants::DEFAULT_CLIENT_ID),
            venue: Venue::from(constants::DEFAULT_VENUE),
            nats: NatsConfig::default(),
            data_format: DataFormat::default(),
            subscriptions: SubscriptionConfig::default(),
            buffer_size: 10000,
            heartbeat_interval_secs: 30,
            enable_message_filtering: true,
            debug_mode: false,
        }
    }
}

impl FourOtcDataClientConfig {
    /// Creates a new configuration with the specified client ID and venue
    pub fn new(client_id: ClientId, venue: Venue) -> Self {
        Self {
            client_id,
            venue,
            ..Default::default()
        }
    }
    
    /// Creates a configuration for development/testing with relaxed settings
    pub fn development() -> Self {
        let mut config = Self::default();
        config.debug_mode = true;
        config.heartbeat_interval_secs = 10;
        config.nats.connection_timeout_secs = 5;
        config.nats.reconnect_delay_ms = 500;
        config
    }
    
    /// Creates a configuration for production with optimized settings
    pub fn production() -> Self {
        let mut config = Self::default();
        config.debug_mode = false;
        config.enable_message_filtering = true;
        config.buffer_size = 50000;
        config.nats.enable_jetstream = true;
        config.nats.jetstream_consumer = Some(JetStreamConsumerConfig::default());
        config
    }
    
    /// Validates the configuration and returns errors if any
    pub fn validate(&self) -> Result<(), ConfigError> {
        if self.client_id.as_str().is_empty() {
            return Err(ConfigError::InvalidClientId);
        }
        
        if self.venue.as_str().is_empty() {
            return Err(ConfigError::InvalidVenue);
        }
        
        if self.nats.servers.is_empty() {
            return Err(ConfigError::EmptyNatsServers);
        }
        
        if self.nats.subject_prefix.is_empty() {
            return Err(ConfigError::EmptySubjectPrefix);
        }
        
        if self.buffer_size == 0 {
            return Err(ConfigError::InvalidBufferSize);
        }
        
        // Validate NATS URLs
        for server in &self.nats.servers {
            if !server.starts_with("nats://") && !server.starts_with("tls://") {
                return Err(ConfigError::InvalidNatsUrl(server.clone()));
            }
        }
        
        Ok(())
    }
    
    /// Returns the connection timeout as a Duration
    pub fn connection_timeout(&self) -> Duration {
        Duration::from_secs(self.nats.connection_timeout_secs)
    }
    
    /// Returns the reconnect delay as a Duration
    pub fn reconnect_delay(&self) -> Duration {
        Duration::from_millis(self.nats.reconnect_delay_ms)
    }
    
    /// Returns the heartbeat interval as a Duration
    pub fn heartbeat_interval(&self) -> Duration {
        Duration::from_secs(self.heartbeat_interval_secs)
    }
}

/// Configuration validation errors
#[derive(Debug, thiserror::Error)]
pub enum ConfigError {
    /// Invalid client ID
    #[error("Client ID cannot be empty")]
    InvalidClientId,
    
    /// Invalid venue
    #[error("Venue cannot be empty")]
    InvalidVenue,
    
    /// Empty NATS servers list
    #[error("NATS servers list cannot be empty")]
    EmptyNatsServers,
    
    /// Invalid NATS URL format
    #[error("Invalid NATS URL format: {0}")]
    InvalidNatsUrl(String),
    
    /// Empty subject prefix
    #[error("NATS subject prefix cannot be empty")]
    EmptySubjectPrefix,
    
    /// Invalid buffer size
    #[error("Buffer size must be greater than 0")]
    InvalidBufferSize,
}

#[cfg(test)]
mod tests {
    use super::*;
    
    #[test]
    fn test_default_config_validation() {
        let config = FourOtcDataClientConfig::default();
        assert!(config.validate().is_ok());
    }
    
    #[test]
    fn test_development_config() {
        let config = FourOtcDataClientConfig::development();
        assert!(config.debug_mode);
        assert_eq!(config.heartbeat_interval_secs, 10);
        assert!(config.validate().is_ok());
    }
    
    #[test]
    fn test_production_config() {
        let config = FourOtcDataClientConfig::production();
        assert!(!config.debug_mode);
        assert!(config.enable_message_filtering);
        assert_eq!(config.buffer_size, 50000);
        assert!(config.nats.enable_jetstream);
        assert!(config.validate().is_ok());
    }
    
    #[test]
    fn test_invalid_client_id() {
        let mut config = FourOtcDataClientConfig::default();
        config.client_id = ClientId::from("");
        assert!(matches!(config.validate(), Err(ConfigError::InvalidClientId)));
    }
    
    #[test]
    fn test_invalid_nats_url() {
        let mut config = FourOtcDataClientConfig::default();
        config.nats.servers = vec!["invalid-url".to_string()];
        assert!(matches!(config.validate(), Err(ConfigError::InvalidNatsUrl(_))));
    }
    
    #[test]
    fn test_empty_buffer_size() {
        let mut config = FourOtcDataClientConfig::default();
        config.buffer_size = 0;
        assert!(matches!(config.validate(), Err(ConfigError::InvalidBufferSize)));
    }
    
    #[test]
    fn test_duration_conversions() {
        let config = FourOtcDataClientConfig::default();
        assert_eq!(config.connection_timeout(), Duration::from_secs(10));
        assert_eq!(config.reconnect_delay(), Duration::from_millis(1000));
        assert_eq!(config.heartbeat_interval(), Duration::from_secs(30));
    }
}