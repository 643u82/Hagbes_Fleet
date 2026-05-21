# -*- coding: utf-8 -*-
"""
Structured Logging and Audit Trail System
Stage 1 Core Infrastructure - Non-intrusive logging framework

This module provides structured logging and audit trail management for the
production safeguards system. It handles event logging, correlation IDs,
and audit trails without affecting existing fleet functionality.

SAFETY CONSTRAINTS:
- NO external alert triggering
- NO system modification logic
- NO database operations beyond logging
- ALL failures must be graceful and non-breaking
"""

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Dict, Any, Optional, Union, List
from enum import Enum
from dataclasses import dataclass, field, asdict
from contextlib import contextmanager

from .deployment_config import get_config, get_environment, Environment

_logger = logging.getLogger(__name__)


class EventType(Enum):
    """Event types for structured logging"""
    DEPLOYMENT_EVENT = "deployment_event"
    VALIDATION_EVENT = "validation_event"
    RUNTIME_EVENT = "runtime_event"
    SECURITY_EVENT = "security_event"
    WORKFLOW_EVENT = "workflow_event"
    BACKUP_EVENT = "backup_event"
    ALERT_EVENT = "alert_event"
    CONFIG_EVENT = "config_event"


class Severity(Enum):
    """Severity levels for events"""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


@dataclass
class EventContext:
    """Context information for events"""
    correlation_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    user_id: Optional[int] = None
    session_id: Optional[str] = None
    request_id: Optional[str] = None
    module_name: str = "hagbes_fleet"
    component: Optional[str] = None
    operation: Optional[str] = None
    environment: str = field(default_factory=lambda: get_environment().value)


@dataclass
class SafeguardEvent:
    """Structured event for safeguards logging"""
    event_type: EventType
    severity: Severity
    message: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    context: EventContext = field(default_factory=EventContext)
    data: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert event to dictionary for JSON serialization"""
        try:
            result = asdict(self)
            # Convert datetime to ISO format
            result['timestamp'] = self.timestamp.isoformat()
            # Convert enums to values
            result['event_type'] = self.event_type.value
            result['severity'] = self.severity.value
            return result
        except Exception as e:
            # Fallback to basic dict
            return {
                'event_type': self.event_type.value if hasattr(self.event_type, 'value') else str(self.event_type),
                'severity': self.severity.value if hasattr(self.severity, 'value') else str(self.severity),
                'message': str(self.message),
                'timestamp': self.timestamp.isoformat() if hasattr(self.timestamp, 'isoformat') else str(self.timestamp),
                'error': f"Serialization error: {e}"
            }
    
    def to_json(self) -> str:
        """Convert event to JSON string"""
        try:
            return json.dumps(self.to_dict(), indent=2, ensure_ascii=False)
        except Exception as e:
            # Fallback to basic JSON
            return json.dumps({
                'event_type': str(self.event_type),
                'severity': str(self.severity),
                'message': str(self.message),
                'timestamp': str(self.timestamp),
                'error': f"JSON serialization error: {e}"
            })


class StructuredLogger:
    """
    Structured logger wrapper for safeguards events.
    
    Provides structured logging with correlation IDs, event types,
    and audit trail management without affecting system operations.
    
    SAFETY: All operations are logging-only and non-intrusive.
    """
    
    def __init__(self, component: str = "safeguards"):
        """
        Initialize structured logger.
        
        Args:
            component: Component name for logging context
        """
        self.component = component
        self.logger = logging.getLogger(f"hagbes_fleet.safeguards.{component}")
        self._correlation_id = None
        
        # Configure logger format for structured output
        self._configure_logger()
    
    def _configure_logger(self) -> None:
        """Configure logger for structured output"""
        try:
            # Only configure if not already configured
            if not self.logger.handlers:
                handler = logging.StreamHandler()
                formatter = logging.Formatter(
                    '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
                )
                handler.setFormatter(formatter)
                self.logger.addHandler(handler)
                self.logger.setLevel(logging.INFO)
        except Exception as e:
            # Fallback to basic logging
            _logger.error(f"Logger configuration failed: {e}")
    
    def set_correlation_id(self, correlation_id: str) -> None:
        """
        Set correlation ID for this logger instance.
        
        Args:
            correlation_id: Correlation ID to use
        """
        self._correlation_id = correlation_id
    
    def get_correlation_id(self) -> str:
        """
        Get current correlation ID, generating one if needed.
        
        Returns:
            str: Current correlation ID
        """
        if self._correlation_id is None:
            self._correlation_id = str(uuid.uuid4())
        return self._correlation_id
    
    def _create_event_context(self, **kwargs) -> EventContext:
        """
        Create event context with current information.
        
        Args:
            **kwargs: Additional context parameters
            
        Returns:
            EventContext: Created context
        """
        try:
            context = EventContext(
                correlation_id=self.get_correlation_id(),
                component=self.component,
                **kwargs
            )
            return context
        except Exception as e:
            _logger.error(f"Event context creation failed: {e}")
            # Return minimal context
            return EventContext(component=self.component)
    
    def _log_event(self, event: SafeguardEvent) -> None:
        """
        Log structured event.
        
        Args:
            event: Event to log
        """
        try:
            # Log as structured JSON
            json_message = event.to_json()
            
            # Map severity to logging level
            level_map = {
                Severity.DEBUG: logging.DEBUG,
                Severity.INFO: logging.INFO,
                Severity.WARNING: logging.WARNING,
                Severity.ERROR: logging.ERROR,
                Severity.CRITICAL: logging.CRITICAL,
            }
            
            level = level_map.get(event.severity, logging.INFO)
            self.logger.log(level, json_message)
            
        except Exception as e:
            # Fallback to basic logging
            try:
                self.logger.error(f"Structured logging failed: {e}, Event: {event.message}")
            except Exception:
                # Ultimate fallback
                _logger.error(f"All logging failed for event: {event.message}")
    
    def log_deployment_event(self, message: str, severity: Severity = Severity.INFO, 
                           operation: Optional[str] = None, **data) -> str:
        """
        Log deployment-related event.
        
        Args:
            message: Event message
            severity: Event severity
            operation: Operation being performed
            **data: Additional event data
            
        Returns:
            str: Correlation ID for the event
        """
        try:
            context = self._create_event_context(operation=operation)
            event = SafeguardEvent(
                event_type=EventType.DEPLOYMENT_EVENT,
                severity=severity,
                message=message,
                context=context,
                data=data,
                tags=["deployment", "safeguards"]
            )
            self._log_event(event)
            return context.correlation_id
        except Exception as e:
            _logger.error(f"Deployment event logging failed: {e}")
            return self.get_correlation_id()
    
    def log_validation_event(self, message: str, severity: Severity = Severity.INFO,
                           validation_type: Optional[str] = None, result: Optional[Dict] = None, **data) -> str:
        """
        Log validation-related event.
        
        Args:
            message: Event message
            severity: Event severity
            validation_type: Type of validation performed
            result: Validation result data
            **data: Additional event data
            
        Returns:
            str: Correlation ID for the event
        """
        try:
            context = self._create_event_context(operation=validation_type)
            event_data = data.copy()
            if result:
                event_data['validation_result'] = result
            
            event = SafeguardEvent(
                event_type=EventType.VALIDATION_EVENT,
                severity=severity,
                message=message,
                context=context,
                data=event_data,
                tags=["validation", "safeguards", validation_type] if validation_type else ["validation", "safeguards"]
            )
            self._log_event(event)
            return context.correlation_id
        except Exception as e:
            _logger.error(f"Validation event logging failed: {e}")
            return self.get_correlation_id()
    
    def log_runtime_event(self, message: str, severity: Severity = Severity.INFO,
                         metric_name: Optional[str] = None, metric_value: Optional[Union[int, float]] = None, **data) -> str:
        """
        Log runtime monitoring event.
        
        Args:
            message: Event message
            severity: Event severity
            metric_name: Name of the metric
            metric_value: Value of the metric
            **data: Additional event data
            
        Returns:
            str: Correlation ID for the event
        """
        try:
            context = self._create_event_context(operation="runtime_monitoring")
            event_data = data.copy()
            if metric_name and metric_value is not None:
                event_data['metric'] = {
                    'name': metric_name,
                    'value': metric_value,
                    'timestamp': datetime.now(timezone.utc).isoformat()
                }
            
            event = SafeguardEvent(
                event_type=EventType.RUNTIME_EVENT,
                severity=severity,
                message=message,
                context=context,
                data=event_data,
                tags=["runtime", "monitoring", "safeguards"]
            )
            self._log_event(event)
            return context.correlation_id
        except Exception as e:
            _logger.error(f"Runtime event logging failed: {e}")
            return self.get_correlation_id()
    
    def log_security_event(self, message: str, severity: Severity = Severity.WARNING,
                          security_type: Optional[str] = None, user_id: Optional[int] = None, **data) -> str:
        """
        Log security-related event.
        
        Args:
            message: Event message
            severity: Event severity
            security_type: Type of security event
            user_id: User ID involved in the event
            **data: Additional event data
            
        Returns:
            str: Correlation ID for the event
        """
        try:
            context = self._create_event_context(operation=security_type, user_id=user_id)
            event = SafeguardEvent(
                event_type=EventType.SECURITY_EVENT,
                severity=severity,
                message=message,
                context=context,
                data=data,
                tags=["security", "safeguards", security_type] if security_type else ["security", "safeguards"]
            )
            self._log_event(event)
            return context.correlation_id
        except Exception as e:
            _logger.error(f"Security event logging failed: {e}")
            return self.get_correlation_id()
    
    def log_workflow_event(self, message: str, severity: Severity = Severity.INFO,
                          workflow_type: Optional[str] = None, state_from: Optional[str] = None,
                          state_to: Optional[str] = None, **data) -> str:
        """
        Log workflow-related event.
        
        Args:
            message: Event message
            severity: Event severity
            workflow_type: Type of workflow
            state_from: Previous state
            state_to: New state
            **data: Additional event data
            
        Returns:
            str: Correlation ID for the event
        """
        try:
            context = self._create_event_context(operation=workflow_type)
            event_data = data.copy()
            if state_from and state_to:
                event_data['state_transition'] = {
                    'from': state_from,
                    'to': state_to,
                    'timestamp': datetime.now(timezone.utc).isoformat()
                }
            
            event = SafeguardEvent(
                event_type=EventType.WORKFLOW_EVENT,
                severity=severity,
                message=message,
                context=context,
                data=event_data,
                tags=["workflow", "safeguards", workflow_type] if workflow_type else ["workflow", "safeguards"]
            )
            self._log_event(event)
            return context.correlation_id
        except Exception as e:
            _logger.error(f"Workflow event logging failed: {e}")
            return self.get_correlation_id()
    
    @contextmanager
    def operation_context(self, operation: str, **context_data):
        """
        Context manager for operation logging.
        
        Args:
            operation: Operation name
            **context_data: Additional context data
        """
        correlation_id = str(uuid.uuid4())
        old_correlation_id = self._correlation_id
        
        try:
            self.set_correlation_id(correlation_id)
            self.log_deployment_event(
                f"Operation started: {operation}",
                severity=Severity.INFO,
                operation=operation,
                **context_data
            )
            yield correlation_id
            
        except Exception as e:
            self.log_deployment_event(
                f"Operation failed: {operation} - {e}",
                severity=Severity.ERROR,
                operation=operation,
                error=str(e),
                **context_data
            )
            raise
            
        else:
            self.log_deployment_event(
                f"Operation completed: {operation}",
                severity=Severity.INFO,
                operation=operation,
                **context_data
            )
            
        finally:
            self._correlation_id = old_correlation_id


class AuditTrailManager:
    """
    Audit trail management for safeguards operations.
    
    Provides audit trail functionality for compliance and investigation
    without affecting system operations.
    
    SAFETY: All operations are logging-only and non-intrusive.
    """
    
    def __init__(self):
        """Initialize audit trail manager"""
        self.logger = StructuredLogger("audit")
    
    def record_configuration_change(self, component: str, old_value: Any, new_value: Any,
                                  changed_by: Optional[str] = None) -> str:
        """
        Record configuration change in audit trail.
        
        Args:
            component: Component that changed
            old_value: Previous value
            new_value: New value
            changed_by: User who made the change
            
        Returns:
            str: Correlation ID for the audit record
        """
        try:
            return self.logger.log_deployment_event(
                f"Configuration changed for {component}",
                severity=Severity.INFO,
                operation="config_change",
                component=component,
                old_value=str(old_value),
                new_value=str(new_value),
                changed_by=changed_by or "system"
            )
        except Exception as e:
            _logger.error(f"Configuration change audit failed: {e}")
            return str(uuid.uuid4())
    
    def record_validation_execution(self, validation_type: str, result: Dict[str, Any],
                                  duration_ms: Optional[float] = None) -> str:
        """
        Record validation execution in audit trail.
        
        Args:
            validation_type: Type of validation
            result: Validation result
            duration_ms: Execution duration in milliseconds
            
        Returns:
            str: Correlation ID for the audit record
        """
        try:
            return self.logger.log_validation_event(
                f"Validation executed: {validation_type}",
                severity=Severity.INFO,
                validation_type=validation_type,
                result=result,
                duration_ms=duration_ms
            )
        except Exception as e:
            _logger.error(f"Validation execution audit failed: {e}")
            return str(uuid.uuid4())
    
    def record_security_check(self, check_type: str, resource: str, user_id: Optional[int] = None,
                            access_granted: bool = True, reason: Optional[str] = None) -> str:
        """
        Record security check in audit trail.
        
        Args:
            check_type: Type of security check
            resource: Resource being accessed
            user_id: User performing the access
            access_granted: Whether access was granted
            reason: Reason for access decision
            
        Returns:
            str: Correlation ID for the audit record
        """
        try:
            severity = Severity.INFO if access_granted else Severity.WARNING
            return self.logger.log_security_event(
                f"Security check: {check_type} for {resource}",
                severity=severity,
                security_type=check_type,
                user_id=user_id,
                resource=resource,
                access_granted=access_granted,
                reason=reason
            )
        except Exception as e:
            _logger.error(f"Security check audit failed: {e}")
            return str(uuid.uuid4())


# Global instances for easy access
structured_logger = StructuredLogger("safeguards")
audit_manager = AuditTrailManager()


def get_logger(component: str = "safeguards") -> StructuredLogger:
    """
    Get structured logger for component.
    
    Args:
        component: Component name
        
    Returns:
        StructuredLogger: Logger instance
    """
    return StructuredLogger(component)


def log_safeguard_event(event_type: EventType, message: str, severity: Severity = Severity.INFO, **data) -> str:
    """
    Log safeguard event globally.
    
    Args:
        event_type: Type of event
        message: Event message
        severity: Event severity
        **data: Additional event data
        
    Returns:
        str: Correlation ID for the event
    """
    try:
        if event_type == EventType.DEPLOYMENT_EVENT:
            return structured_logger.log_deployment_event(message, severity, **data)
        elif event_type == EventType.VALIDATION_EVENT:
            return structured_logger.log_validation_event(message, severity, **data)
        elif event_type == EventType.RUNTIME_EVENT:
            return structured_logger.log_runtime_event(message, severity, **data)
        elif event_type == EventType.SECURITY_EVENT:
            return structured_logger.log_security_event(message, severity, **data)
        elif event_type == EventType.WORKFLOW_EVENT:
            return structured_logger.log_workflow_event(message, severity, **data)
        else:
            return structured_logger.log_deployment_event(message, severity, **data)
    except Exception as e:
        _logger.error(f"Global event logging failed: {e}")
        return str(uuid.uuid4())