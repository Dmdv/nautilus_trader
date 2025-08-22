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

//! Build script for generating protobuf code from 4OTC market data schema.

use std::{env, path::PathBuf};

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let proto_file = "../../../../va-md-adapter-4otc/marketdata/proto/market_data.proto";
    let proto_dir = "../../../../va-md-adapter-4otc/marketdata/proto/";
    
    // Check if proto file exists
    let proto_path = PathBuf::from(proto_file);
    if !proto_path.exists() {
        println!("cargo:warning=Proto file not found at {}", proto_file);
        println!("cargo:warning=Skipping protobuf generation");
        return Ok(());
    }
    
    println!("cargo:rerun-if-changed={}", proto_file);
    
    // Configure prost build
    let mut config = prost_build::Config::new();
    
    // Generate code with proper module structure
    config.out_dir("src/proto");
    
    // Compile the protobuf files
    config.compile_protos(&[proto_file], &[proto_dir])?;
    
    println!("cargo:warning=Generated protobuf code from {}", proto_file);
    
    Ok(())
}