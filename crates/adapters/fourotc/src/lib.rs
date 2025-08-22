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

//! NautilusTrader adapter for 4OTC market data integration.
//!
//! This adapter provides integration with 4OTC market data feeds through NATS messaging.
//! It includes both direct WebSocket connectivity and NATS-based data consumption capabilities.
//!
//! # Architecture
//!
//! The adapter consists of several key components:
//! - **NATS Data Client**: Consumes market data from NATS streams published by the 4OTC adapter
//! - **Data Conversion**: Converts 4OTC SBE-decoded messages to Nautilus data types  
//! - **WebSocket Client**: Direct connection to 4OTC WebSocket feeds (future enhancement)
//! - **Configuration**: Flexible configuration for different deployment scenarios
//!
//! # Usage
//!
//! The adapter can be used in two modes:
//! 1. **NATS Mode**: Consumes data from NATS streams (recommended for production)
//! 2. **Direct Mode**: Direct WebSocket connection to 4OTC (future feature)

#![warn(missing_docs)]
#![deny(unsafe_code)]

pub mod client;
pub mod config;
pub mod convert;
pub mod enums;
pub mod proto;
pub mod types;

/// Common constants used throughout the adapter
pub mod constants {
    /// Default NATS server URL
    pub const DEFAULT_NATS_URL: &str = "nats://localhost:4222";
    
    /// Default subject prefix for 4OTC market data
    pub const DEFAULT_SUBJECT_PREFIX: &str = "market.4otc";
    
    /// Default venue identifier for 4OTC
    pub const DEFAULT_VENUE: &str = "4OTC";
    
    /// Default client ID for the data client
    pub const DEFAULT_CLIENT_ID: &str = "FOUROTC-001";
}

/// Re-exports for convenience
pub use client::FourOtcDataClient;
pub use config::{FourOtcDataClientConfig, NatsConfig};
pub use types::{FourOtcInstrument, FourOtcSymbol};

#[cfg(feature = "python")]
pub mod python;