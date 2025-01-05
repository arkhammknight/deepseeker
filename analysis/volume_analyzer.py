"""
Volume analysis module for detecting suspicious trading patterns and fake volume.

This module implements advanced volume analysis algorithms to detect wash trading,
manipulated volume, and other suspicious trading patterns.
"""

import logging
import numpy as np
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass
import aiohttp
from collections import defaultdict

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@dataclass
class OrderBookMetrics:
    """Metrics calculated from order book analysis."""
    depth_ratio: float  # Ratio of buy depth to sell depth
    spread_percentage: float  # Bid-ask spread as percentage
    concentration_score: float  # Order concentration score (0-1)
    wall_detection: bool  # Whether significant walls are detected
    manipulation_score: float  # Overall manipulation score (0-1)

@dataclass
class VolumeAnalysis:
    """Results of volume analysis."""
    wash_trading_score: float  # Likelihood of wash trading (0-1)
    volume_legitimacy_score: float  # Overall volume legitimacy (0-1)
    suspicious_patterns: List[str]  # List of detected suspicious patterns
    risk_level: str  # HIGH, MEDIUM, or LOW
    timestamp: datetime

class VolumeAnalyzer:
    """Analyzer for detecting suspicious trading volume patterns."""

    def __init__(self):
        """Initialize the volume analyzer."""
        self.analysis_cache = {}
        self.historical_data = defaultdict(list)
        self.session = None

    async def __aenter__(self):
        """Create aiohttp session when entering context."""
        self.session = aiohttp.ClientSession()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Close aiohttp session when exiting context."""
        if self.session:
            await self.session.close()

    async def analyze_order_book(self, order_book: Dict) -> OrderBookMetrics:
        """
        Analyze order book for suspicious patterns.

        Args:
            order_book: Dictionary containing bids and asks

        Returns:
            OrderBookMetrics: Calculated metrics from order book analysis
        """
        try:
            bids = order_book.get('bids', [])
            asks = order_book.get('asks', [])

            if not bids or not asks:
                return OrderBookMetrics(
                    depth_ratio=0.0,
                    spread_percentage=0.0,
                    concentration_score=0.0,
                    wall_detection=False,
                    manipulation_score=1.0
                )

            # Calculate buy/sell depth ratio
            buy_depth = sum(float(bid[0]) * float(bid[1]) for bid in bids)
            sell_depth = sum(float(ask[0]) * float(ask[1]) for ask in asks)
            depth_ratio = buy_depth / sell_depth if sell_depth > 0 else 0.0

            # Calculate bid-ask spread
            best_bid = float(bids[0][0])
            best_ask = float(asks[0][0])
            spread_percentage = (best_ask - best_bid) / best_ask if best_ask > 0 else 0.0

            # Detect order walls (large orders that may indicate manipulation)
            avg_bid_size = np.mean([float(bid[1]) for bid in bids])
            avg_ask_size = np.mean([float(ask[1]) for ask in asks])
            max_bid_size = max([float(bid[1]) for bid in bids])
            max_ask_size = max([float(ask[1]) for ask in asks])

            wall_detection = (max_bid_size > avg_bid_size * 5 or 
                            max_ask_size > avg_ask_size * 5)

            # Calculate order concentration
            bid_concentration = self._calculate_concentration([float(bid[1]) for bid in bids])
            ask_concentration = self._calculate_concentration([float(ask[1]) for ask in asks])
            concentration_score = (bid_concentration + ask_concentration) / 2

            # Calculate overall manipulation score
            manipulation_score = self._calculate_manipulation_score(
                depth_ratio, spread_percentage, concentration_score, wall_detection
            )

            return OrderBookMetrics(
                depth_ratio=depth_ratio,
                spread_percentage=spread_percentage,
                concentration_score=concentration_score,
                wall_detection=wall_detection,
                manipulation_score=manipulation_score
            )

        except Exception as e:
            logger.error(f"Error analyzing order book: {str(e)}")
            return OrderBookMetrics(0.0, 0.0, 0.0, False, 1.0)

    def _calculate_concentration(self, sizes: List[float]) -> float:
        """
        Calculate concentration of order sizes.

        Args:
            sizes: List of order sizes

        Returns:
            float: Concentration score (0-1)
        """
        if not sizes:
            return 0.0

        total_size = sum(sizes)
        if total_size == 0:
            return 0.0

        # Calculate Herfindahl-Hirschman Index
        normalized_sizes = [size / total_size for size in sizes]
        hhi = sum(size * size for size in normalized_sizes)
        
        # Normalize HHI to 0-1 range
        normalized_hhi = (hhi - (1 / len(sizes))) / (1 - (1 / len(sizes)))
        return max(0.0, min(1.0, normalized_hhi))

    def _calculate_manipulation_score(self,
                                   depth_ratio: float,
                                   spread_percentage: float,
                                   concentration_score: float,
                                   wall_detection: bool) -> float:
        """
        Calculate overall manipulation score.

        Args:
            depth_ratio: Ratio of buy depth to sell depth
            spread_percentage: Bid-ask spread percentage
            concentration_score: Order concentration score
            wall_detection: Whether walls were detected

        Returns:
            float: Manipulation score (0-1)
        """
        # Normalize depth ratio (should be close to 1 for healthy markets)
        depth_score = abs(1 - depth_ratio) if depth_ratio > 0 else 1.0

        # Calculate weighted score
        weights = {
            'depth': 0.3,
            'spread': 0.2,
            'concentration': 0.3,
            'walls': 0.2
        }

        score = (
            weights['depth'] * depth_score +
            weights['spread'] * min(spread_percentage * 5, 1.0) +
            weights['concentration'] * concentration_score +
            weights['walls'] * (1.0 if wall_detection else 0.0)
        )

        return min(1.0, score)

    async def analyze_volume_patterns(self, 
                                   token_data: Dict,
                                   timeframe_hours: int = 24) -> VolumeAnalysis:
        """
        Analyze trading volume patterns for legitimacy.

        Args:
            token_data: Token trading data
            timeframe_hours: Timeframe to analyze in hours

        Returns:
            VolumeAnalysis: Results of volume analysis
        """
        try:
            # Extract relevant data
            volume_history = token_data.get('volume_history', [])
            trades = token_data.get('trades', [])
            order_book = token_data.get('order_book', {})

            suspicious_patterns = []
            
            # Analyze order book
            order_metrics = await self.analyze_order_book(order_book)
            
            # Check for wash trading indicators
            wash_trading_score = await self._detect_wash_trading(trades)
            if wash_trading_score > 0.7:
                suspicious_patterns.append("High probability of wash trading detected")

            # Analyze volume consistency
            volume_consistency = self._analyze_volume_consistency(volume_history)
            if volume_consistency < 0.3:
                suspicious_patterns.append("Highly inconsistent volume patterns")

            # Calculate overall volume legitimacy score
            legitimacy_score = 1.0 - (
                0.4 * wash_trading_score +
                0.3 * order_metrics.manipulation_score +
                0.3 * (1.0 - volume_consistency)
            )

            # Determine risk level
            risk_level = "HIGH" if legitimacy_score < 0.3 else \
                        "MEDIUM" if legitimacy_score < 0.7 else \
                        "LOW"

            analysis = VolumeAnalysis(
                wash_trading_score=wash_trading_score,
                volume_legitimacy_score=legitimacy_score,
                suspicious_patterns=suspicious_patterns,
                risk_level=risk_level,
                timestamp=datetime.now()
            )

            # Cache the analysis
            self.analysis_cache[token_data.get('address')] = analysis

            return analysis

        except Exception as e:
            logger.error(f"Error analyzing volume patterns: {str(e)}")
            return VolumeAnalysis(1.0, 0.0, ["Analysis failed"], "HIGH", datetime.now())

    async def _detect_wash_trading(self, trades: List[Dict]) -> float:
        """
        Detect wash trading patterns in trade history.

        Args:
            trades: List of trade data

        Returns:
            float: Wash trading likelihood score (0-1)
        """
        if not trades:
            return 1.0

        try:
            # Group trades by address
            address_trades = defaultdict(list)
            for trade in trades:
                address_trades[trade.get('maker_address')].append(trade)
                address_trades[trade.get('taker_address')].append(trade)

            # Calculate metrics
            circular_trading_score = 0.0
            frequent_reversal_score = 0.0
            
            for address, addr_trades in address_trades.items():
                # Check for circular trading
                if len(addr_trades) > 2:
                    buy_volume = sum(float(t.get('amount', 0)) 
                                   for t in addr_trades if t.get('side') == 'buy')
                    sell_volume = sum(float(t.get('amount', 0)) 
                                    for t in addr_trades if t.get('side') == 'sell')
                    
                    if min(buy_volume, sell_volume) / max(buy_volume, sell_volume) > 0.8:
                        circular_trading_score += 1

                # Check for frequent direction reversals
                if len(addr_trades) > 3:
                    reversals = 0
                    for i in range(1, len(addr_trades)):
                        if addr_trades[i].get('side') != addr_trades[i-1].get('side'):
                            reversals += 1
                    reversal_ratio = reversals / (len(addr_trades) - 1)
                    frequent_reversal_score = max(frequent_reversal_score, reversal_ratio)

            # Normalize scores
            num_active_addresses = len(address_trades)
            if num_active_addresses > 0:
                circular_trading_score = min(1.0, circular_trading_score / num_active_addresses)

            # Combine scores
            return 0.6 * circular_trading_score + 0.4 * frequent_reversal_score

        except Exception as e:
            logger.error(f"Error detecting wash trading: {str(e)}")
            return 1.0

    def _analyze_volume_consistency(self, volume_history: List[float]) -> float:
        """
        Analyze consistency of trading volume.

        Args:
            volume_history: List of historical volume data

        Returns:
            float: Volume consistency score (0-1)
        """
        if not volume_history:
            return 0.0

        try:
            # Calculate volume volatility
            volume_array = np.array(volume_history)
            if len(volume_array) < 2:
                return 0.0

            # Calculate coefficient of variation
            mean_volume = np.mean(volume_array)
            std_volume = np.std(volume_array)
            cv = std_volume / mean_volume if mean_volume > 0 else float('inf')

            # Calculate volume trend
            volume_changes = np.diff(volume_array)
            trend_consistency = np.mean(np.sign(volume_changes[:-1]) == np.sign(volume_changes[1:]))

            # Combine metrics
            consistency_score = 1.0 - min(1.0, cv / 2)  # Normalize CV
            consistency_score = 0.7 * consistency_score + 0.3 * trend_consistency

            return max(0.0, min(1.0, consistency_score))

        except Exception as e:
            logger.error(f"Error analyzing volume consistency: {str(e)}")
            return 0.0

    def get_cached_analysis(self, token_address: str) -> Optional[VolumeAnalysis]:
        """
        Get cached analysis results for a token.

        Args:
            token_address: Token address to check

        Returns:
            Optional[VolumeAnalysis]: Cached analysis if available
        """
        return self.analysis_cache.get(token_address)
