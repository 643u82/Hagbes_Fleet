# -*- coding: utf-8 -*-
"""
Alert Management System
Stage 1 Core Infrastructure - Alert abstraction layer (passive mode only)

This module provides alert abstraction and management for the production
safeguards system. In Stage 1, it operates in log-only mode without
external notifications or system interruption.

SAFETY CONSTRAINTS:
- NO email/SMS sending
- NO rollback triggers
- NO runtime interruption
- ALL alerts are log-only in Stage 1
- ALL failures must be graceful and non-breaking
"""

import hashlib
import time
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional, List, Set
from enum import Enum
from dataclasses import dataclass, field
from collections import defaultdict, deque

from .deployment_config import get_config, is_feature_enabled, FeatureToggle
from .logging_audit_system import get_logger, EventType, Severity, StructuredLogger

_logger = get_logger("alert_manager")


class AlertSeverity(Enum):
    """Alert severity levels"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class AlertCategory(Enum):
    """Alert categories for classification"""
    DEPLOYMENT = "deployment"
    VALIDATION = "validation"
    SECURITY = "security"
    PERFORMANCE = "performance"
    WORKFLOW = "workflow"
    SYSTEM = "system"
    BACKUP = "backup"


class AlertChannel(Enum):
    """Alert delivery channels"""
    LOG = "log"  # Only enabled channel in Stage 1
    EMAIL = "email"  # Disabled in Stage 1
    SMS = "sms"  # Disabled in Stage 1
    DASHBOARD = "dashboard"  # Disabled in Stage 1
    WEBHOOK = "webhook"  # Disabled in Stage 1


@dataclass
class Alert:
    """Alert data structure"""
    id: str
    title: str
    message: str
    severity: AlertSeverity
    category: AlertCategory
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    source_component: str = "safeguards"
    correlation_id: Optional[str] = None
    data: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    resolved: bool = False
    resolved_at: Optional[datetime] = None
    resolved_by: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert alert to dictionary"""
        return {
            'id': self.id,
            'title': self.title,
            'message': self.message,
            'severity': self.severity.value,
            'category': self.category.value,
            'timestamp': self.timestamp.isoformat(),
            'source_component': self.source_component,
            'correlation_id': self.correlation_id,
            'data': self.data,
            'tags': self.tags,
            'resolved': self.resolved,
            'resolved_at': self.resolved_at.isoformat() if self.resolved_at else None,
            'resolved_by': self.resolved_by,
        }


@dataclass
class AlertRule:
    """Alert rule configuration"""
    name: str
    category: AlertCategory
    severity: AlertSeverity
    condition: str  # Description of the condition
    threshold: Optional[float] = None
    time_window_minutes: int = 15
    max_alerts_per_window: int = 5
    enabled: bool = True
    channels: List[AlertChannel] = field(default_factory=lambda: [AlertChannel.LOG])


class AlertDeduplicator:
    """
    Alert deduplication system to prevent alert spam.
    
    Groups similar alerts and manages alert frequency to prevent
    overwhelming the monitoring system.
    """
    
    def __init__(self, window_minutes: int = 15):
        """
        Initialize deduplicator.
        
        Args:
            window_minutes: Time window for deduplication
        """
        self.window_minutes = window_minutes
        self.alert_counts: Dict[str, deque] = defaultdict(deque)
        self.last_cleanup = time.time()
    
    def _generate_alert_key(self, alert: Alert) -> str:
        """
        Generate deduplication key for alert.
        
        Args:
            alert: Alert to generate key for
            
        Returns:
            str: Deduplication key
        """
        try:
            # Create key from category, severity, and message hash
            message_hash = hashlib.md5(alert.message.encode()).hexdigest()[:8]
            return f"{alert.category.value}:{alert.severity.value}:{message_hash}"
        except Exception as e:
            _logger.log_runtime_event(
                f"Alert key generation failed: {e}",
                severity=Severity.WARNING,
                alert_id=alert.id
            )
            return f"unknown:{alert.id}"
    
    def _cleanup_old_entries(self) -> None:
        """Clean up old entries from deduplication tracking"""
        try:
            current_time = time.time()
            # Only cleanup every 5 minutes to avoid overhead
            if current_time - self.last_cleanup < 300:
                return
            
            cutoff_time = current_time - (self.window_minutes * 60)
            
            for key in list(self.alert_counts.keys()):
                timestamps = self.alert_counts[key]
                # Remove old timestamps
                while timestamps and timestamps[0] < cutoff_time:
                    timestamps.popleft()
                
                # Remove empty entries
                if not timestamps:
                    del self.alert_counts[key]
            
            self.last_cleanup = current_time
            
        except Exception as e:
            _logger.log_runtime_event(
                f"Alert deduplication cleanup failed: {e}",
                severity=Severity.WARNING
            )
    
    def should_send_alert(self, alert: Alert, max_per_window: int = 5) -> bool:
        """
        Check if alert should be sent based on deduplication rules.
        
        Args:
            alert: Alert to check
            max_per_window: Maximum alerts per time window
            
        Returns:
            bool: True if alert should be sent
        """
        try:
            self._cleanup_old_entries()
            
            key = self._generate_alert_key(alert)
            current_time = time.time()
            
            # Add current alert timestamp
            self.alert_counts[key].append(current_time)
            
            # Check if we're within limits
            count = len(self.alert_counts[key])
            should_send = count <= max_per_window
            
            if not should_send:
                _logger.log_runtime_event(
                    f"Alert suppressed due to deduplication: {alert.title}",
                    severity=Severity.INFO,
                    alert_key=key,
                    count=count,
                    max_per_window=max_per_window
                )
            
            return should_send
            
        except Exception as e:
            _logger.log_runtime_event(
                f"Alert deduplication check failed: {e}",
                severity=Severity.WARNING,
                alert_id=alert.id
            )
            # Default to allowing the alert on error
            return True


class AlertThrottler:
    """
    Alert throttling system to manage alert frequency.
    
    Prevents alert storms by limiting the rate of alerts
    across all categories and channels.
    """
    
    def __init__(self, max_alerts_per_hour: int = 20):
        """
        Initialize throttler.
        
        Args:
            max_alerts_per_hour: Maximum alerts per hour
        """
        self.max_alerts_per_hour = max_alerts_per_hour
        self.alert_timestamps: deque = deque()
    
    def _cleanup_old_timestamps(self) -> None:
        """Clean up timestamps older than 1 hour"""
        try:
            cutoff_time = time.time() - 3600  # 1 hour ago
            while self.alert_timestamps and self.alert_timestamps[0] < cutoff_time:
                self.alert_timestamps.popleft()
        except Exception as e:
            _logger.log_runtime_event(
                f"Alert throttler cleanup failed: {e}",
                severity=Severity.WARNING
            )
    
    def should_allow_alert(self, alert: Alert) -> bool:
        """
        Check if alert should be allowed based on throttling rules.
        
        Args:
            alert: Alert to check
            
        Returns:
            bool: True if alert should be allowed
        """
        try:
            self._cleanup_old_timestamps()
            
            current_time = time.time()
            
            # Critical alerts always allowed
            if alert.severity == AlertSeverity.CRITICAL:
                self.alert_timestamps.append(current_time)
                return True
            
            # Check if we're within limits
            if len(self.alert_timestamps) >= self.max_alerts_per_hour:
                _logger.log_runtime_event(
                    f"Alert throttled: {alert.title}",
                    severity=Severity.INFO,
                    alert_count=len(self.alert_timestamps),
                    max_per_hour=self.max_alerts_per_hour
                )
                return False
            
            self.alert_timestamps.append(current_time)
            return True
            
        except Exception as e:
            _logger.log_runtime_event(
                f"Alert throttling check failed: {e}",
                severity=Severity.WARNING,
                alert_id=alert.id
            )
            # Default to allowing the alert on error
            return True


class AlertManager:
    """
    Alert management system for production safeguards.
    
    Provides alert classification, deduplication, throttling, and
    delivery coordination. In Stage 1, operates in log-only mode.
    
    SAFETY: All operations are logging-only and non-intrusive in Stage 1.
    """
    
    def __init__(self):
        """Initialize alert manager"""
        self.logger = get_logger("alert_manager")
        self.deduplicator = AlertDeduplicator()
        self.throttler = AlertThrottler()
        self.active_alerts: Dict[str, Alert] = {}
        self.alert_rules: Dict[str, AlertRule] = {}
        self._initialize_default_rules()
    
    def _initialize_default_rules(self) -> None:
        """Initialize default alert rules for Stage 1"""
        try:
            default_rules = [
                AlertRule(
                    name="deployment_failure",
                    category=AlertCategory.DEPLOYMENT,
                    severity=AlertSeverity.HIGH,
                    condition="Deployment validation fails",
                    channels=[AlertChannel.LOG]
                ),
                AlertRule(
                    name="validation_error",
                    category=AlertCategory.VALIDATION,
                    severity=AlertSeverity.MEDIUM,
                    condition="Validation check fails",
                    channels=[AlertChannel.LOG]
                ),
                AlertRule(
                    name="security_violation",
                    category=AlertCategory.SECURITY,
                    severity=AlertSeverity.HIGH,
                    condition="Security rule violation detected",
                    channels=[AlertChannel.LOG]
                ),
                AlertRule(
                    name="performance_degradation",
                    category=AlertCategory.PERFORMANCE,
                    severity=AlertSeverity.MEDIUM,
                    condition="Performance threshold exceeded",
                    channels=[AlertChannel.LOG]
                ),
                AlertRule(
                    name="workflow_failure",
                    category=AlertCategory.WORKFLOW,
                    severity=AlertSeverity.MEDIUM,
                    condition="Workflow integrity check fails",
                    channels=[AlertChannel.LOG]
                ),
                AlertRule(
                    name="system_error",
                    category=AlertCategory.SYSTEM,
                    severity=AlertSeverity.HIGH,
                    condition="System component failure",
                    channels=[AlertChannel.LOG]
                ),
            ]
            
            for rule in default_rules:
                self.alert_rules[rule.name] = rule
                
        except Exception as e:
            self.logger.log_runtime_event(
                f"Default alert rules initialization failed: {e}",
                severity=Severity.WARNING
            )
    
    def _generate_alert_id(self, title: str, category: AlertCategory) -> str:
        """
        Generate unique alert ID.
        
        Args:
            title: Alert title
            category: Alert category
            
        Returns:
            str: Unique alert ID
        """
        try:
            timestamp = str(int(time.time()))
            content = f"{category.value}:{title}:{timestamp}"
            return hashlib.md5(content.encode()).hexdigest()[:12]
        except Exception as e:
            self.logger.log_runtime_event(
                f"Alert ID generation failed: {e}",
                severity=Severity.WARNING
            )
            return f"alert_{int(time.time())}"
    
    def _should_process_alert(self, alert: Alert) -> bool:
        """
        Check if alert should be processed based on all rules.
        
        Args:
            alert: Alert to check
            
        Returns:
            bool: True if alert should be processed
        """
        try:
            # Check if alert system is enabled
            if not is_feature_enabled(FeatureToggle.ALERT_SYSTEM):
                return False
            
            # Check deduplication
            rule = self.alert_rules.get(f"{alert.category.value}_{alert.severity.value}")
            max_per_window = rule.max_alerts_per_window if rule else 5
            
            if not self.deduplicator.should_send_alert(alert, max_per_window):
                return False
            
            # Check throttling
            if not self.throttler.should_allow_alert(alert):
                return False
            
            return True
            
        except Exception as e:
            self.logger.log_runtime_event(
                f"Alert processing check failed: {e}",
                severity=Severity.WARNING,
                alert_id=alert.id
            )
            # Default to processing the alert on error
            return True
    
    def _deliver_alert_to_log(self, alert: Alert) -> bool:
        """
        Deliver alert to log channel (only enabled channel in Stage 1).
        
        Args:
            alert: Alert to deliver
            
        Returns:
            bool: True if delivery successful
        """
        try:
            # Map alert severity to log severity
            severity_map = {
                AlertSeverity.LOW: Severity.INFO,
                AlertSeverity.MEDIUM: Severity.WARNING,
                AlertSeverity.HIGH: Severity.ERROR,
                AlertSeverity.CRITICAL: Severity.CRITICAL,
            }
            
            log_severity = severity_map.get(alert.severity, Severity.INFO)
            
            # Log the alert
            self.logger.log_runtime_event(
                f"ALERT: {alert.title} - {alert.message}",
                severity=log_severity,
                metric_name="alert_generated",
                metric_value=1,
                alert_id=alert.id,
                alert_category=alert.category.value,
                alert_severity=alert.severity.value,
                alert_data=alert.data,
                alert_tags=alert.tags
            )
            
            return True
            
        except Exception as e:
            self.logger.log_runtime_event(
                f"Alert log delivery failed: {e}",
                severity=Severity.ERROR,
                alert_id=alert.id
            )
            return False
    
    def _deliver_alert(self, alert: Alert) -> Dict[AlertChannel, bool]:
        """
        Deliver alert to configured channels.
        
        Args:
            alert: Alert to deliver
            
        Returns:
            Dict[AlertChannel, bool]: Delivery results by channel
        """
        results = {}
        
        try:
            # In Stage 1, only log channel is enabled
            enabled_channels = [AlertChannel.LOG]
            
            for channel in enabled_channels:
                try:
                    if channel == AlertChannel.LOG:
                        results[channel] = self._deliver_alert_to_log(alert)
                    else:
                        # Other channels disabled in Stage 1
                        results[channel] = False
                        
                except Exception as e:
                    self.logger.log_runtime_event(
                        f"Alert delivery failed for channel {channel.value}: {e}",
                        severity=Severity.WARNING,
                        alert_id=alert.id,
                        channel=channel.value
                    )
                    results[channel] = False
            
            return results
            
        except Exception as e:
            self.logger.log_runtime_event(
                f"Alert delivery coordination failed: {e}",
                severity=Severity.ERROR,
                alert_id=alert.id
            )
            return {AlertChannel.LOG: False}
    
    def create_alert(self, title: str, message: str, severity: AlertSeverity,
                    category: AlertCategory, source_component: str = "safeguards",
                    correlation_id: Optional[str] = None, **data) -> Optional[str]:
        """
        Create and process new alert.
        
        Args:
            title: Alert title
            message: Alert message
            severity: Alert severity
            category: Alert category
            source_component: Source component name
            correlation_id: Correlation ID for tracking
            **data: Additional alert data
            
        Returns:
            Optional[str]: Alert ID if created successfully
        """
        try:
            # Generate alert ID
            alert_id = self._generate_alert_id(title, category)
            
            # Create alert object
            alert = Alert(
                id=alert_id,
                title=title,
                message=message,
                severity=severity,
                category=category,
                source_component=source_component,
                correlation_id=correlation_id,
                data=data,
                tags=[category.value, severity.value, source_component]
            )
            
            # Check if alert should be processed
            if not self._should_process_alert(alert):
                return None
            
            # Store active alert
            self.active_alerts[alert_id] = alert
            
            # Deliver alert
            delivery_results = self._deliver_alert(alert)
            
            # Log alert creation
            self.logger.log_runtime_event(
                f"Alert created: {title}",
                severity=Severity.INFO,
                alert_id=alert_id,
                alert_category=category.value,
                alert_severity=severity.value,
                delivery_results=delivery_results
            )
            
            return alert_id
            
        except Exception as e:
            self.logger.log_runtime_event(
                f"Alert creation failed: {e}",
                severity=Severity.ERROR,
                title=title,
                category=category.value if category else "unknown"
            )
            return None
    
    def resolve_alert(self, alert_id: str, resolved_by: str = "system") -> bool:
        """
        Resolve an active alert.
        
        Args:
            alert_id: Alert ID to resolve
            resolved_by: Who resolved the alert
            
        Returns:
            bool: True if resolved successfully
        """
        try:
            if alert_id not in self.active_alerts:
                self.logger.log_runtime_event(
                    f"Alert not found for resolution: {alert_id}",
                    severity=Severity.WARNING,
                    alert_id=alert_id
                )
                return False
            
            alert = self.active_alerts[alert_id]
            alert.resolved = True
            alert.resolved_at = datetime.now(timezone.utc)
            alert.resolved_by = resolved_by
            
            # Log resolution
            self.logger.log_runtime_event(
                f"Alert resolved: {alert.title}",
                severity=Severity.INFO,
                alert_id=alert_id,
                resolved_by=resolved_by
            )
            
            # Remove from active alerts
            del self.active_alerts[alert_id]
            
            return True
            
        except Exception as e:
            self.logger.log_runtime_event(
                f"Alert resolution failed: {e}",
                severity=Severity.ERROR,
                alert_id=alert_id
            )
            return False
    
    def get_active_alerts(self, category: Optional[AlertCategory] = None,
                         severity: Optional[AlertSeverity] = None) -> List[Alert]:
        """
        Get list of active alerts with optional filtering.
        
        Args:
            category: Filter by category
            severity: Filter by severity
            
        Returns:
            List[Alert]: List of matching active alerts
        """
        try:
            alerts = list(self.active_alerts.values())
            
            if category:
                alerts = [a for a in alerts if a.category == category]
            
            if severity:
                alerts = [a for a in alerts if a.severity == severity]
            
            # Sort by timestamp (newest first)
            alerts.sort(key=lambda a: a.timestamp, reverse=True)
            
            return alerts
            
        except Exception as e:
            self.logger.log_runtime_event(
                f"Active alerts retrieval failed: {e}",
                severity=Severity.WARNING
            )
            return []
    
    def get_alert_statistics(self) -> Dict[str, Any]:
        """
        Get alert system statistics.
        
        Returns:
            Dict[str, Any]: Alert statistics
        """
        try:
            active_alerts = list(self.active_alerts.values())
            
            stats = {
                'total_active_alerts': len(active_alerts),
                'alerts_by_severity': {},
                'alerts_by_category': {},
                'oldest_alert': None,
                'newest_alert': None,
                'alert_system_enabled': is_feature_enabled(FeatureToggle.ALERT_SYSTEM),
                'monitor_mode': is_feature_enabled(FeatureToggle.MONITOR_MODE),
            }
            
            if active_alerts:
                # Count by severity
                for severity in AlertSeverity:
                    count = len([a for a in active_alerts if a.severity == severity])
                    stats['alerts_by_severity'][severity.value] = count
                
                # Count by category
                for category in AlertCategory:
                    count = len([a for a in active_alerts if a.category == category])
                    stats['alerts_by_category'][category.value] = count
                
                # Oldest and newest
                sorted_alerts = sorted(active_alerts, key=lambda a: a.timestamp)
                stats['oldest_alert'] = sorted_alerts[0].timestamp.isoformat()
                stats['newest_alert'] = sorted_alerts[-1].timestamp.isoformat()
            
            return stats
            
        except Exception as e:
            self.logger.log_runtime_event(
                f"Alert statistics generation failed: {e}",
                severity=Severity.WARNING
            )
            return {
                'total_active_alerts': 0,
                'error': str(e)
            }


# Global alert manager instance
alert_manager = AlertManager()


def create_deployment_alert(title: str, message: str, severity: AlertSeverity = AlertSeverity.MEDIUM,
                          correlation_id: Optional[str] = None, **data) -> Optional[str]:
    """
    Create deployment-related alert.
    
    Args:
        title: Alert title
        message: Alert message
        severity: Alert severity
        correlation_id: Correlation ID
        **data: Additional data
        
    Returns:
        Optional[str]: Alert ID if created
    """
    return alert_manager.create_alert(
        title=title,
        message=message,
        severity=severity,
        category=AlertCategory.DEPLOYMENT,
        correlation_id=correlation_id,
        **data
    )


def create_validation_alert(title: str, message: str, severity: AlertSeverity = AlertSeverity.MEDIUM,
                          validation_type: Optional[str] = None, correlation_id: Optional[str] = None, **data) -> Optional[str]:
    """
    Create validation-related alert.
    
    Args:
        title: Alert title
        message: Alert message
        severity: Alert severity
        validation_type: Type of validation
        correlation_id: Correlation ID
        **data: Additional data
        
    Returns:
        Optional[str]: Alert ID if created
    """
    if validation_type:
        data['validation_type'] = validation_type
    
    return alert_manager.create_alert(
        title=title,
        message=message,
        severity=severity,
        category=AlertCategory.VALIDATION,
        correlation_id=correlation_id,
        **data
    )


def create_security_alert(title: str, message: str, severity: AlertSeverity = AlertSeverity.HIGH,
                         security_type: Optional[str] = None, correlation_id: Optional[str] = None, **data) -> Optional[str]:
    """
    Create security-related alert.
    
    Args:
        title: Alert title
        message: Alert message
        severity: Alert severity
        security_type: Type of security issue
        correlation_id: Correlation ID
        **data: Additional data
        
    Returns:
        Optional[str]: Alert ID if created
    """
    if security_type:
        data['security_type'] = security_type
    
    return alert_manager.create_alert(
        title=title,
        message=message,
        severity=severity,
        category=AlertCategory.SECURITY,
        correlation_id=correlation_id,
        **data
    )


def resolve_alert(alert_id: str, resolved_by: str = "system") -> bool:
    """
    Resolve alert globally.
    
    Args:
        alert_id: Alert ID to resolve
        resolved_by: Who resolved the alert
        
    Returns:
        bool: True if resolved successfully
    """
    return alert_manager.resolve_alert(alert_id, resolved_by)


def get_active_alerts(category: Optional[AlertCategory] = None,
                     severity: Optional[AlertSeverity] = None) -> List[Alert]:
    """
    Get active alerts globally.
    
    Args:
        category: Filter by category
        severity: Filter by severity
        
    Returns:
        List[Alert]: List of active alerts
    """
    return alert_manager.get_active_alerts(category, severity)