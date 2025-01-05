"""
Pattern analyzer module for analyzing detected patterns and generating insights.

This module processes detected patterns, combines multiple signals, and generates
actionable insights about potential rug pulls, pumps, or other significant events.
"""

import logging
from typing import Dict, List, Optional, Set
from datetime import datetime, timedelta
from dataclasses import dataclass
from .pattern_detector import PatternDetector, PatternAlert, PatternType

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@dataclass
class AnalysisResult:
    """Data class for storing analysis results."""
    token_address: str
    risk_score: float
    patterns_detected: List[PatternAlert]
    timestamp: datetime
    recommendation: str
    details: Dict

class PatternAnalyzer:
    """Class for analyzing patterns and generating insights."""

    def __init__(self):
        """Initialize the pattern analyzer."""
        self.pattern_detector = PatternDetector()
        self.analysis_history: Dict[str, List[AnalysisResult]] = {}
        self.high_risk_tokens: Set[str] = set()

    async def analyze_token(self, token_data: Dict) -> AnalysisResult:
        """
        Analyze token data for patterns and generate insights.

        Args:
            token_data: Dictionary containing token trading data

        Returns:
            AnalysisResult: Analysis results including risk score and recommendations
        """
        try:
            token_address = token_data.get('token_address', '')
            patterns_detected = []
            
            # Detect liquidity drops
            current_liquidity = token_data.get('liquidity_usd', 0)
            historical_liquidity = token_data.get('historical_liquidity', [])
            liquidity_alert = self.pattern_detector.detect_liquidity_drop(
                current_liquidity, historical_liquidity
            )
            if liquidity_alert:
                liquidity_alert.token_address = token_address
                patterns_detected.append(liquidity_alert)

            # Detect pump patterns
            price_data = token_data.get('price_history', [])
            volume_data = token_data.get('volume_history', [])
            timestamps = token_data.get('timestamps', [])
            if price_data and volume_data and timestamps:
                pump_alert = self.pattern_detector.detect_pump_pattern(
                    price_data, volume_data, timestamps
                )
                if pump_alert:
                    pump_alert.token_address = token_address
                    patterns_detected.append(pump_alert)

            # Detect unusual volume
            current_volume = token_data.get('volume_24h', 0)
            historical_volumes = token_data.get('historical_volumes', [])
            volume_alert = self.pattern_detector.detect_unusual_volume(
                current_volume, historical_volumes
            )
            if volume_alert:
                volume_alert.token_address = token_address
                patterns_detected.append(volume_alert)

            # Calculate combined risk score
            risk_score = self._calculate_risk_score(patterns_detected)
            
            # Generate recommendation
            recommendation = self._generate_recommendation(
                risk_score, patterns_detected
            )

            # Create analysis result
            result = AnalysisResult(
                token_address=token_address,
                risk_score=risk_score,
                patterns_detected=patterns_detected,
                timestamp=datetime.now(),
                recommendation=recommendation,
                details=self._generate_analysis_details(patterns_detected)
            )

            # Update history
            if token_address not in self.analysis_history:
                self.analysis_history[token_address] = []
            self.analysis_history[token_address].append(result)

            # Update high risk tokens
            if risk_score >= 0.8:
                self.high_risk_tokens.add(token_address)
            elif token_address in self.high_risk_tokens:
                self.high_risk_tokens.remove(token_address)

            return result

        except Exception as e:
            logger.error(f"Error analyzing token patterns: {str(e)}")
            return AnalysisResult(
                token_address=token_address,
                risk_score=0.0,
                patterns_detected=[],
                timestamp=datetime.now(),
                recommendation="Analysis failed due to error",
                details={'error': str(e)}
            )

    def _calculate_risk_score(self, patterns: List[PatternAlert]) -> float:
        """
        Calculate overall risk score based on detected patterns.

        Args:
            patterns: List of detected patterns

        Returns:
            float: Risk score between 0 and 1
        """
        if not patterns:
            return 0.0

        # Weight different pattern types
        pattern_weights = {
            PatternType.RUG_PULL: 1.0,
            PatternType.PUMP_AND_DUMP: 0.8,
            PatternType.HONEYPOT: 0.9,
            PatternType.LARGE_SELLS: 0.7,
            PatternType.UNUSUAL_VOLUME: 0.6
        }

        weighted_scores = []
        for pattern in patterns:
            weight = pattern_weights.get(pattern.pattern_type, 0.5)
            weighted_scores.append(pattern.confidence * weight)

        return min(sum(weighted_scores) / len(weighted_scores), 1.0)

    def _generate_recommendation(self, 
                               risk_score: float, 
                               patterns: List[PatternAlert]) -> str:
        """
        Generate recommendation based on risk score and patterns.

        Args:
            risk_score: Calculated risk score
            patterns: List of detected patterns

        Returns:
            str: Recommendation message
        """
        if risk_score >= 0.8:
            return "HIGH RISK: Immediate attention required. Multiple high-risk patterns detected."
        elif risk_score >= 0.6:
            return "MEDIUM RISK: Exercise caution. Suspicious patterns detected."
        elif risk_score >= 0.4:
            return "LOW RISK: Monitor situation. Some unusual patterns detected."
        else:
            return "SAFE: No significant risk patterns detected."

    def _generate_analysis_details(self, patterns: List[PatternAlert]) -> Dict:
        """
        Generate detailed analysis information.

        Args:
            patterns: List of detected patterns

        Returns:
            Dict: Detailed analysis information
        """
        details = {
            'pattern_count': len(patterns),
            'pattern_types': [],
            'severity_distribution': {'HIGH': 0, 'MEDIUM': 0, 'LOW': 0}
        }

        for pattern in patterns:
            details['pattern_types'].append(pattern.pattern_type.value)
            details['severity_distribution'][pattern.severity] += 1

        return details

    def get_token_history(self, token_address: str) -> List[AnalysisResult]:
        """
        Get analysis history for a specific token.

        Args:
            token_address: Token address to get history for

        Returns:
            List[AnalysisResult]: List of historical analysis results
        """
        return self.analysis_history.get(token_address, [])

    def get_high_risk_tokens(self) -> Set[str]:
        """
        Get set of high risk tokens.

        Returns:
            Set[str]: Set of token addresses marked as high risk
        """
        return self.high_risk_tokens.copy()

    def clear_history(self) -> None:
        """Clear analysis history."""
        self.analysis_history.clear()
        self.high_risk_tokens.clear()
