"""
Pattern detection module for identifying suspicious token behavior.

This module implements algorithms to detect various patterns that might indicate
rug pulls, pumps, or other significant events in token trading.
"""

import logging
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
import numpy as np
from dataclasses import dataclass
from enum import Enum

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class PatternType(Enum):
    """Enumeration of different pattern types that can be detected."""
    RUG_PULL = "rug_pull"
    PUMP_AND_DUMP = "pump_and_dump"
    HONEYPOT = "honeypot"
    CEX_LISTING = "cex_listing"
    LARGE_SELLS = "large_sells"
    UNUSUAL_VOLUME = "unusual_volume"

@dataclass
class PatternAlert:
    """Data class for storing pattern detection results."""
    pattern_type: PatternType
    confidence: float
    timestamp: datetime
    details: Dict
    token_address: str
    severity: str

class PatternDetector:
    """Class for detecting various trading patterns."""

    def __init__(self):
        """Initialize the pattern detector with default thresholds."""
        self.thresholds = {
            'liquidity_drop': 0.3,  # 30% drop
            'price_pump': 0.5,      # 50% increase
            'volume_spike': 5.0,     # 5x normal volume
            'sell_pressure': 0.7,    # 70% sells vs buys
            'time_window': 3600,     # 1 hour in seconds
        }
        self.pattern_history = []

    def detect_liquidity_drop(self, 
                            current_liquidity: float, 
                            historical_liquidity: List[float],
                            time_window: int = 3600) -> Optional[PatternAlert]:
        """
        Detect sudden drops in liquidity that might indicate a rug pull.

        Args:
            current_liquidity: Current liquidity value
            historical_liquidity: List of historical liquidity values
            time_window: Time window in seconds to analyze

        Returns:
            Optional[PatternAlert]: Alert if pattern detected, None otherwise
        """
        try:
            if not historical_liquidity:
                return None

            # Calculate percentage change
            prev_liquidity = historical_liquidity[-1]
            if prev_liquidity == 0:
                return None

            change = (current_liquidity - prev_liquidity) / prev_liquidity

            if change <= -self.thresholds['liquidity_drop']:
                confidence = min(abs(change) * 2, 1.0)
                severity = 'HIGH' if change <= -0.5 else 'MEDIUM'

                return PatternAlert(
                    pattern_type=PatternType.RUG_PULL,
                    confidence=confidence,
                    timestamp=datetime.now(),
                    details={
                        'liquidity_change': change,
                        'current_liquidity': current_liquidity,
                        'previous_liquidity': prev_liquidity
                    },
                    token_address='',  # To be filled by caller
                    severity=severity
                )

            return None
        except Exception as e:
            logger.error(f"Error in liquidity drop detection: {str(e)}")
            return None

    def detect_pump_pattern(self, 
                          price_data: List[float], 
                          volume_data: List[float],
                          timestamps: List[datetime]) -> Optional[PatternAlert]:
        """
        Detect pump patterns based on price and volume movements.

        Args:
            price_data: List of historical prices
            volume_data: List of historical volumes
            timestamps: List of corresponding timestamps

        Returns:
            Optional[PatternAlert]: Alert if pattern detected, None otherwise
        """
        try:
            if len(price_data) < 2 or len(volume_data) < 2:
                return None

            # Calculate price change
            price_change = (price_data[-1] - price_data[0]) / price_data[0]
            
            # Calculate volume change
            avg_volume = np.mean(volume_data[:-1])
            current_volume = volume_data[-1]
            volume_change = current_volume / avg_volume if avg_volume > 0 else 0

            if (price_change >= self.thresholds['price_pump'] and 
                volume_change >= self.thresholds['volume_spike']):
                
                confidence = min((price_change / self.thresholds['price_pump']) * 0.7 +
                               (volume_change / self.thresholds['volume_spike']) * 0.3, 1.0)
                
                return PatternAlert(
                    pattern_type=PatternType.PUMP_AND_DUMP,
                    confidence=confidence,
                    timestamp=datetime.now(),
                    details={
                        'price_change': price_change,
                        'volume_change': volume_change,
                        'time_frame': str(timestamps[-1] - timestamps[0])
                    },
                    token_address='',
                    severity='HIGH' if confidence > 0.8 else 'MEDIUM'
                )

            return None
        except Exception as e:
            logger.error(f"Error in pump pattern detection: {str(e)}")
            return None

    def detect_unusual_volume(self, 
                            current_volume: float, 
                            historical_volumes: List[float]) -> Optional[PatternAlert]:
        """
        Detect unusual trading volume patterns.

        Args:
            current_volume: Current trading volume
            historical_volumes: List of historical trading volumes

        Returns:
            Optional[PatternAlert]: Alert if pattern detected, None otherwise
        """
        try:
            if not historical_volumes:
                return None

            avg_volume = np.mean(historical_volumes)
            if avg_volume == 0:
                return None

            volume_ratio = current_volume / avg_volume

            if volume_ratio >= self.thresholds['volume_spike']:
                confidence = min(volume_ratio / self.thresholds['volume_spike'], 1.0)
                
                return PatternAlert(
                    pattern_type=PatternType.UNUSUAL_VOLUME,
                    confidence=confidence,
                    timestamp=datetime.now(),
                    details={
                        'volume_ratio': volume_ratio,
                        'current_volume': current_volume,
                        'average_volume': avg_volume
                    },
                    token_address='',
                    severity='HIGH' if volume_ratio > 10 else 'MEDIUM'
                )

            return None
        except Exception as e:
            logger.error(f"Error in unusual volume detection: {str(e)}")
            return None

    def detect_sell_pressure(self, 
                           buy_volume: float, 
                           sell_volume: float) -> Optional[PatternAlert]:
        """
        Detect high sell pressure that might indicate dumping.

        Args:
            buy_volume: Volume of buy orders
            sell_volume: Volume of sell orders

        Returns:
            Optional[PatternAlert]: Alert if pattern detected, None otherwise
        """
        try:
            total_volume = buy_volume + sell_volume
            if total_volume == 0:
                return None

            sell_ratio = sell_volume / total_volume

            if sell_ratio >= self.thresholds['sell_pressure']:
                confidence = min((sell_ratio - 0.5) * 2, 1.0)
                
                return PatternAlert(
                    pattern_type=PatternType.LARGE_SELLS,
                    confidence=confidence,
                    timestamp=datetime.now(),
                    details={
                        'sell_ratio': sell_ratio,
                        'buy_volume': buy_volume,
                        'sell_volume': sell_volume
                    },
                    token_address='',
                    severity='HIGH' if sell_ratio > 0.8 else 'MEDIUM'
                )

            return None
        except Exception as e:
            logger.error(f"Error in sell pressure detection: {str(e)}")
            return None

    def update_thresholds(self, new_thresholds: Dict) -> None:
        """
        Update detection thresholds.

        Args:
            new_thresholds: Dictionary of new threshold values
        """
        self.thresholds.update(new_thresholds)

    def get_pattern_history(self) -> List[PatternAlert]:
        """
        Get history of detected patterns.

        Returns:
            List[PatternAlert]: List of historical pattern alerts
        """
        return self.pattern_history

    def clear_pattern_history(self) -> None:
        """Clear the pattern history."""
        self.pattern_history.clear()
