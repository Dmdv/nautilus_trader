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

//! Python bindings for 4OTC configuration types.

use nautilus_model::identifiers::{ClientId, Venue};
use pyo3::prelude::*;

use crate::config::{FourOtcDataClientConfig, NatsConfig};

#[pymethods]
impl FourOtcDataClientConfig {
    #[new]
    #[pyo3(signature = (client_id, venue, nats_servers=None, nats_subject_prefix=None, debug_mode=false))]
    fn py_new(
        client_id: ClientId,
        venue: Venue,
        nats_servers: Option<Vec<String>>,
        nats_subject_prefix: Option<String>,
        debug_mode: Option<bool>,
    ) -> Self {
        let mut config = Self::new(client_id, venue);
        
        if let Some(servers) = nats_servers {
            config.nats.servers = servers;
        }
        
        if let Some(prefix) = nats_subject_prefix {
            config.nats.subject_prefix = prefix;
        }
        
        if let Some(debug) = debug_mode {
            config.debug_mode = debug;
        }
        
        config
    }
    
    #[staticmethod]
    fn development() -> Self {
        Self::development()
    }
    
    #[staticmethod]
    fn production() -> Self {
        Self::production()
    }
    
    fn validate(&self) -> PyResult<()> {
        self.validate()
            .map_err(|e| PyErr::new::<pyo3::exceptions::PyValueError, _>(e.to_string()))
    }
    
    #[getter]
    fn client_id(&self) -> ClientId {
        self.client_id
    }
    
    #[getter]
    fn venue(&self) -> Venue {
        self.venue
    }
    
    #[getter]
    fn debug_mode(&self) -> bool {
        self.debug_mode
    }
    
    #[getter]
    fn buffer_size(&self) -> usize {
        self.buffer_size
    }
    
    #[getter]
    fn heartbeat_interval_secs(&self) -> u64 {
        self.heartbeat_interval_secs
    }
    
    fn __repr__(&self) -> String {
        format!(
            "FourOtcDataClientConfig(client_id={}, venue={}, debug_mode={})",
            self.client_id, self.venue, self.debug_mode
        )
    }
}

#[pymethods]
impl NatsConfig {
    #[new]
    #[pyo3(signature = (servers=None, subject_prefix=None, client_name=None))]
    fn py_new(
        servers: Option<Vec<String>>,
        subject_prefix: Option<String>,
        client_name: Option<String>,
    ) -> Self {
        let mut config = Self::default();
        
        if let Some(servers) = servers {
            config.servers = servers;
        }
        
        if let Some(prefix) = subject_prefix {
            config.subject_prefix = prefix;
        }
        
        if let Some(name) = client_name {
            config.client_name = name;
        }
        
        config
    }
    
    #[getter]
    fn servers(&self) -> Vec<String> {
        self.servers.clone()
    }
    
    #[getter]
    fn subject_prefix(&self) -> String {
        self.subject_prefix.clone()
    }
    
    #[getter]
    fn client_name(&self) -> String {
        self.client_name.clone()
    }
    
    #[getter]
    fn connection_timeout_secs(&self) -> u64 {
        self.connection_timeout_secs
    }
    
    fn __repr__(&self) -> String {
        format!(
            "NatsConfig(servers={:?}, subject_prefix={}, client_name={})",
            self.servers, self.subject_prefix, self.client_name
        )
    }
}

/// Python API wrapper for `FourOtcDataClientConfig`
#[pyclass(module = "nautilus_trader.core.nautilus_pyo3.adapters.fourotc", name = "FourOtcDataClientConfig")]
#[derive(Clone, Debug)]
pub struct FourOtcDataClientConfig_API {
    pub inner: FourOtcDataClientConfig,
}

#[pymethods]
impl FourOtcDataClientConfig_API {
    #[new]
    #[pyo3(signature = (client_id, venue, nats_servers=None, nats_subject_prefix=None, debug_mode=false))]
    fn py_new(
        client_id: ClientId,
        venue: Venue,
        nats_servers: Option<Vec<String>>,
        nats_subject_prefix: Option<String>,
        debug_mode: Option<bool>,
    ) -> Self {
        Self {
            inner: FourOtcDataClientConfig::py_new(
                client_id,
                venue,
                nats_servers,
                nats_subject_prefix,
                debug_mode,
            ),
        }
    }
    
    #[staticmethod]
    fn development() -> Self {
        Self {
            inner: FourOtcDataClientConfig::development(),
        }
    }
    
    #[staticmethod]
    fn production() -> Self {
        Self {
            inner: FourOtcDataClientConfig::production(),
        }
    }
    
    fn validate(&self) -> PyResult<()> {
        self.inner.validate()
    }
    
    #[getter]
    fn client_id(&self) -> ClientId {
        self.inner.client_id()
    }
    
    #[getter]
    fn venue(&self) -> Venue {
        self.inner.venue()
    }
    
    #[getter]
    fn debug_mode(&self) -> bool {
        self.inner.debug_mode()
    }
    
    #[getter]
    fn buffer_size(&self) -> usize {
        self.inner.buffer_size()
    }
    
    #[getter]
    fn heartbeat_interval_secs(&self) -> u64 {
        self.inner.heartbeat_interval_secs()
    }
    
    fn __repr__(&self) -> String {
        self.inner.__repr__()
    }
}

/// Python API wrapper for `NatsConfig`
#[pyclass(module = "nautilus_trader.core.nautilus_pyo3.adapters.fourotc", name = "NatsConfig")]
#[derive(Clone, Debug)]
pub struct NatsConfig_API {
    pub inner: NatsConfig,
}

#[pymethods]
impl NatsConfig_API {
    #[new]
    #[pyo3(signature = (servers=None, subject_prefix=None, client_name=None))]
    fn py_new(
        servers: Option<Vec<String>>,
        subject_prefix: Option<String>,
        client_name: Option<String>,
    ) -> Self {
        Self {
            inner: NatsConfig::py_new(servers, subject_prefix, client_name),
        }
    }
    
    #[getter]
    fn servers(&self) -> Vec<String> {
        self.inner.servers()
    }
    
    #[getter]
    fn subject_prefix(&self) -> String {
        self.inner.subject_prefix()
    }
    
    #[getter]
    fn client_name(&self) -> String {
        self.inner.client_name()
    }
    
    #[getter]
    fn connection_timeout_secs(&self) -> u64 {
        self.inner.connection_timeout_secs()
    }
    
    fn __repr__(&self) -> String {
        self.inner.__repr__()
    }
}