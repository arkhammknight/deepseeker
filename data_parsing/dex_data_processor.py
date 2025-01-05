"""
DexScreener data processor for parsing and analyzing token data.

This module processes and analyzes data retrieved from the DexScreener API,
preparing it for further analysis and storage.
"""

import logging
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class DexDataProcessor:
    """Processor for DexScreener API data."""
    
    def __init__(self):
        """Initialize the DexScreener data processor."""
        self.processed_data = {}
        
    def process_token_data(self, raw_data: Dict) -> Dict:
        """
        Process raw token data from DexScreener API.
        
        Args:
            raw_data (Dict): Raw token data from API
            
        Returns:
            Dict: Processed token data with relevant metrics
        """
        try:
            if not raw_data or not raw_data.get('pairs'):
                return {}
            
            # Get the most liquid pair
            pairs = raw_data['pairs']
            most_liquid_pair = max(pairs, key=lambda x: float(x.get('liquidity', {}).get('usd', 0)))
            
            processed = {
                'token_address': most_liquid_pair.get('baseToken', {}).get('address'),
                'token_name': most_liquid_pair.get('baseToken', {}).get('name'),
                'token_symbol': most_liquid_pair.get('baseToken', {}).get('symbol'),
                'price_usd': float(most_liquid_pair.get('priceUsd', 0)),
                'price_change_24h': float(most_liquid_pair.get('priceChange24h', 0)),
                'liquidity_usd': float(most_liquid_pair.get('liquidity', {}).get('usd', 0)),
                'volume_24h': float(most_liquid_pair.get('volume', {}).get('h24', 0)),
                'pair_address': most_liquid_pair.get('pairAddress'),
                'dex_id': most_liquid_pair.get('dexId'),
                'chain_id': most_liquid_pair.get('chainId'),
                'timestamp': datetime.now().isoformat(),
            }
            
            # Store processed data
            self.processed_data[processed['token_address']] = processed
            
            return processed
        except Exception as e:
            logger.error(f"Error processing token data: {str(e)}")
            return {}
    
    def analyze_liquidity(self, token_data: Dict) -> Tuple[float, str]:
        """
        Analyze token liquidity and determine risk level.
        
        Args:
            token_data (Dict): Processed token data
            
        Returns:
            Tuple[float, str]: Liquidity score (0-1) and risk level
        """
        try:
            liquidity = token_data.get('liquidity_usd', 0)
            
            # Define liquidity thresholds
            HIGH_LIQUIDITY = 1000000  # $1M
            MEDIUM_LIQUIDITY = 100000  # $100K
            
            if liquidity >= HIGH_LIQUIDITY:
                return (1.0, 'LOW')
            elif liquidity >= MEDIUM_LIQUIDITY:
                return (0.7, 'MEDIUM')
            else:
                return (0.3, 'HIGH')
        except Exception as e:
            logger.error(f"Error analyzing liquidity: {str(e)}")
            return (0.0, 'UNKNOWN')
    
    def analyze_price_movement(self, token_data: Dict) -> Dict:
        """
        Analyze price movements and volatility.
        
        Args:
            token_data (Dict): Processed token data
            
        Returns:
            Dict: Price analysis results
        """
        try:
            price_change = token_data.get('price_change_24h', 0)
            volume = token_data.get('volume_24h', 0)
            liquidity = token_data.get('liquidity_usd', 0)
            
            # Calculate volatility score (simple version)
            volatility_score = abs(price_change) / 100
            
            # Calculate volume/liquidity ratio
            vol_liq_ratio = volume / liquidity if liquidity > 0 else 0
            
            return {
                'volatility_score': min(volatility_score, 1.0),
                'volume_liquidity_ratio': vol_liq_ratio,
                'price_trend': 'UP' if price_change > 0 else 'DOWN' if price_change < 0 else 'STABLE',
                'is_high_volatility': volatility_score > 0.2,  # 20% threshold
                'timestamp': datetime.now().isoformat()
            }
        except Exception as e:
            logger.error(f"Error analyzing price movement: {str(e)}")
            return {}
    
    def get_stored_data(self, token_address: str) -> Optional[Dict]:
        """
        Retrieve stored data for a token.
        
        Args:
            token_address (str): Token contract address
            
        Returns:
            Optional[Dict]: Stored token data if available
        """
        return self.processed_data.get(token_address)
    
    def clear_stored_data(self) -> None:
        """Clear all stored token data."""
        self.processed_data.clear()
    
    def calculate_metrics(self, token_data: Dict) -> Dict:
        """
        Calculate additional metrics for token analysis.
        
        Args:
            token_data (Dict): Processed token data
            
        Returns:
            Dict: Calculated metrics
        """
        try:
            liquidity_score, risk_level = self.analyze_liquidity(token_data)
            price_analysis = self.analyze_price_movement(token_data)
            
            return {
                'token_address': token_data.get('token_address'),
                'timestamp': datetime.now().isoformat(),
                'metrics': {
                    'liquidity_score': liquidity_score,
                    'risk_level': risk_level,
                    'volatility_score': price_analysis.get('volatility_score', 0),
                    'volume_liquidity_ratio': price_analysis.get('volume_liquidity_ratio', 0),
                    'price_trend': price_analysis.get('price_trend', 'UNKNOWN'),
                    'is_high_volatility': price_analysis.get('is_high_volatility', False)
                }
            }
        except Exception as e:
            logger.error(f"Error calculating metrics: {str(e)}")
            return {}
