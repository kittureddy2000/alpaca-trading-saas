
import os
import sys
import yaml
from alpaca.data.historical.option import OptionHistoricalDataClient
from alpaca.data.requests import OptionSnapshotRequest

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def load_env_vars():
    with open('env_vars.yaml', 'r') as f:
        return yaml.safe_load(f)

def test_options_access():
    env = load_env_vars()
    api_key = env.get('ALPACA_CLIENT_ID') # Using the ID as key based on previous context
    secret_key = env.get('ALPACA_CLIENT_SECRET')

    if not api_key or not secret_key:
        print("Error: Alpaca credentials not found in env_vars.yaml")
        return

    print(f"Testing Options Data access with Key: {api_key[:5]}...")

    try:
        # Note: Options Data often requires a separate client or specific subscription
        client = OptionHistoricalDataClient(api_key, secret_key)
        
        # Test with a known active symbol, e.g., SPY or AAPL
        # We need a valid option symbol. Let's try to construct one strictly for testing or just list chain
        # Actually, listing chain might be safer to find a symbol first.
        
        # However, listing chain usually requires 'OptionChainRequest' which might be in a different module
        # Let's try getting a snapshot for a very likely to exist option if we can guess it, 
        # OR just check if we can list options.
        
        # Better approach: check documentation or just try to get latest quote for a stock to verify connection,
        # then try options.
        
        from alpaca.data.requests import OptionChainRequest
        from datetime import datetime
        
        # Try to get chain for AAPL
        req = OptionChainRequest(underlying_symbol='AAPL')
        # This returns a dictionary of snapshots
        print("Requesting Option Chain for AAPL...")
        chain = client.get_option_chain(req)
        
        print("Success! Received option chain data.")
        keys = list(chain.keys())
        print(f"Total options returned: {len(keys)}")
        if keys:
            print(f"Sample Option: {keys[0]}")
            print(f"Sample Data: {chain[keys[0]]}")
            
    except Exception as e:
        print(f"Failed to access Options Data: {e}")

if __name__ == "__main__":
    test_options_access()
