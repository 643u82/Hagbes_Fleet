#!/usr/bin/env python3
"""
HAGBES FLEET LOGGING & AUDIT SYSTEM
===================================

Enterprise logging and audit system that provides comprehensive tracking
of all fleet operations, security events, and system changes.

Features:
- Structured audit logging
- Security event tracking
- Performance monitoring
- Compliance reporting
- Real-time alerting
"""

import os
import sys
import json
import logging
import logging.handlers
from pathlib import Path
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from enum import Enum
import threading
import queue
import time

class AuditEventType(Enum):
    """Audit event types for categorization."""
    SECURITY = "security"
    WORKFLOW = "workflow"
    DATA_CHANGE = "data_change"
    ACCESS_CONTROL = "access_control"
    SYSTEM = "system"
    PERFORMANCE = "performance"
    COMPLIANCE = "compliance"

class AuditSeverity(Enum):
    """Audit event severity levels."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

class FleetAuditLogger:
    """Centralized audit logging system for hagbes_fleet module."""
    
    def __init__(self, config_path: str):
        self.config_path = Path(config_path)
        self.config = self._load_config()
        self.audit_queue = queue.Queue()
        self.processing_thread = None
        self.running = False
        
        # Initialize loggers
        self._setup_loggers()
        
        # Start audit processing
        self.start_audit_processing()
    
    def _load_config(self) -> Dict[str, Any]:
        """Load audit configuration."""
        default_config = {
            'audit_enabled': True,
            'log_directory': '/var/log/hagbes_fleet',
            'log_rotation': {
                'max_bytes': 10 * 1024 * 1024,  # 10MB
                'backup_count': 10
            },
            'audit_levels': {
                'security': 'INFO',
                'workflow': 'INFO',
                'data_change': 'DEBUG',
                'access_control': 'WARNING',
                'system': 'INFO',
                'performance': 'DEBUG',
                'compliance': 'INFO'
            },
            'real_time_alerts': {
                'enabled': True,
                'alert_threshold': {
                    'security_events_per_minute': 10,
                    'failed_logins_per_minute': 5,
                    'access_violations_per_minute': 3
                }
            },
            'retention_days': 365,
            'compliance_reporting': {
                'enabled': True,
                'report_schedule': 'daily',
                'report_recipients': ['admin@company.com']
            }
        }
        
        if self.config_path.exists():
            try:
                with open(self.config_path, 'r') as f:
                    user_config = json.load(f)
                default_config.update(user_config)
            except Exception as e:
                print(f"Warning: Could not load audit config: {e}")
        
        return default_config
    
    def _setup_loggers(self):
        """Setup structured logging system."""
        log_dir = Path(self.config['log_directory'])
        log_dir.mkdir(parents=True, exist_ok=True)
        
        # Main audit logger
        self.audit_logger = logging.getLogger('hagbes_fleet.audit')
        self.audit_logger.setLevel(logging.DEBUG)
        
        # Audit log file handler with rotation
        audit_handler = logging.handlers.RotatingFileHandler(
            log_dir / 'audit.log',
            maxBytes=self.config['log_rotation']['max_bytes'],
            backupCount=self.config['log_rotation']['backup_count']
        )
        
        # JSON formatter for structured logging
        audit_formatter = logging.Formatter(
            '%(asctime)s | %(levelname)s | %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        audit_handler.setFormatter(audit_formatter)
        self.audit_logger.addHandler(audit_handler)
        
        # Security events logger
        self.security_logger = logging.getLogger('hagbes_fleet.security')
        self.security_logger.setLevel(logging.INFO)
        
        security_handler = logging.handlers.RotatingFileHandler(
            log_dir / 'security.log',
            maxBytes=self.config['log_rotation']['max_bytes'],
            backupCount=self.config['log_rotation']['backup_count']
        )
        security_handler.setFormatter(audit_formatter)
        self.security_logger.addHandler(security_handler)
        
        # Performance logger
        self.performance_logger = logging.getLogger('hagbes_fleet.performance')
        self.performance_logger.setLevel(logging.DEBUG)
        
        performance_handler = logging.handlers.RotatingFileHandler(
            log_dir / 'performance.log',
            maxBytes=self.config['log_rotation']['max_bytes'],
            backupCount=self.config['log_rotation']['backup_count']
        )
        performance_handler.setFormatter(audit_formatter)
        self.performance_logger.addHandler(performance_handler)
        
        # Compliance logger
        self.compliance_logger = logging.getLogger('hagbes_fleet.compliance')
        self.compliance_logger.setLevel(logging.INFO)
        
        compliance_handler = logging.handlers.RotatingFileHandler(
            log_dir / 'compliance.log',
            maxBytes=self.config['log_rotation']['max_bytes'],
            backupCount=self.config['log_rotation']['backup_count']
        )
        compliance_handler.setFormatter(audit_formatter)
        self.compliance_logger.addHandler(compliance_handler)
    
    def start_audit_processing(self):
        """Start background audit processing thread."""
        if not self.running:
            self.running = True
            self.processing_thread = threading.Thread(target=self._process_audit_events, daemon=True)
            self.processing_thread.start()
    
    def stop_audit_processing(self):
        """Stop background audit processing."""
        self.running = False
        if self.processing_thread:
            self.processing_thread.join(timeout=5)
    
    def _process_audit_events(self):
        """Process audit events from queue."""
        while self.running:
            try:
                # Get audit event with timeout
                event = self.audit_queue.get(timeout=1)
                self._write_audit_event(event)
                self.audit_queue.task_done()
            except queue.Empty:
                continue
            except Exception as e:
                print(f"Error processing audit event: {e}")
    
    def _write_audit_event(self, event: Dict[str, Any]):
        """Write audit event to appropriate log."""
        event_type = event.get('event_type', AuditEventType.SYSTEM.value)
        severity = event.get('severity', AuditSeverity.LOW.value)
        
        # Format event as JSON
        log_entry = json.dumps(event, default=str)
        
        # Route to appropriate logger
        if event_type == AuditEventType.SECURITY.value:
            if severity == AuditSeverity.CRITICAL.value:
                self.security_logger.critical(log_entry)
            elif severity == AuditSeverity.HIGH.value:
                self.security_logger.error(log_entry)
            elif severity == AuditSeverity.MEDIUM.value:
                self.security_logger.warning(log_entry)
            else:
                self.security_logger.info(log_entry)
        
        elif event_type == AuditEventType.PERFORMANCE.value:
            self.performance_logger.debug(log_entry)
        
        elif event_type == AuditEventType.COMPLIANCE.value:
            self.compliance_logger.info(log_entry)
        
        else:
            # Default to main audit logger
            if severity == AuditSeverity.CRITICAL.value:
                self.audit_logger.critical(log_entry)
            elif severity == AuditSeverity.HIGH.value:
                self.audit_logger.error(log_entry)
            elif severity == AuditSeverity.MEDIUM.value:
                self.audit_logger.warning(log_entry)
            else:
                self.audit_logger.info(log_entry)
    
    def log_security_event(self, event_name: str, user_id: int, details: Dict[str, Any], 
                          severity: AuditSeverity = AuditSeverity.MEDIUM):
        """Log security-related event."""
        event = {
            'timestamp': datetime.now().isoformat(),
            'event_type': AuditEventType.SECURITY.value,
            'event_name': event_name,
            'severity': severity.value,
            'user_id': user_id,
            'details': details,
            'source': 'hagbes_fleet'
        }
        
        if self.config['audit_enabled']:
            self.audit_queue.put(event)
    
    def log_workflow_event(self, event_name: str, requisition_id: int, user_id: int, 
                          old_state: str, new_state: str, details: Dict[str, Any] = None):
        """Log workflow state change event."""
        event = {
            'timestamp': datetime.now().isoformat(),
            'event_type': AuditEventType.WORKFLOW.value,
            'event_name': event_name,
            'severity': AuditSeverity.LOW.value,
            'requisition_id': requisition_id,
            'user_id': user_id,
            'state_transition': {
                'from': old_state,
                'to': new_state
            },
            'details': details or {},
            'source': 'hagbes_fleet'
        }
        
        if self.config['audit_enabled']:
            self.audit_queue.put(event)
    
    def log_data_change(self, model_name: str, record_id: int, user_id: int, 
                       field_changes: Dict[str, Any], operation: str = 'write'):
        """Log data modification event."""
        event = {
            'timestamp': datetime.now().isoformat(),
            'event_type': AuditEventType.DATA_CHANGE.value,
            'event_name': f'{model_name}_{operation}',
            'severity': AuditSeverity.LOW.value,
            'model_name': model_name,
            'record_id': record_id,
            'user_id': user_id,
            'operation': operation,
            'field_changes': field_changes,
            'source': 'hagbes_fleet'
        }
        
        if self.config['audit_enabled']:
            self.audit_queue.put(event)
    
    def log_access_control_event(self, event_name: str, user_id: int, resource: str, 
                               action: str, result: str, details: Dict[str, Any] = None):
        """Log access control event."""
        severity = AuditSeverity.HIGH if result == 'denied' else AuditSeverity.LOW
        
        event = {
            'timestamp': datetime.now().isoformat(),
            'event_type': AuditEventType.ACCESS_CONTROL.value,
            'event_name': event_name,
            'severity': severity.value,
            'user_id': user_id,
            'resource': resource,
            'action': action,
            'result': result,
            'details': details or {},
            'source': 'hagbes_fleet'
        }
        
        if self.config['audit_enabled']:
            self.audit_queue.put(event)
    
    def log_performance_event(self, event_name: str, duration_ms: float, 
                            details: Dict[str, Any] = None):
        """Log performance-related event."""
        # Determine severity based on duration
        if duration_ms > 5000:  # > 5 seconds
            severity = AuditSeverity.HIGH
        elif duration_ms > 2000:  # > 2 seconds
            severity = AuditSeverity.MEDIUM
        else:
            severity = AuditSeverity.LOW
        
        event = {
            'timestamp': datetime.now().isoformat(),
            'event_type': AuditEventType.PERFORMANCE.value,
            'event_name': event_name,
            'severity': severity.value,
            'duration_ms': duration_ms,
            'details': details or {},
            'source': 'hagbes_fleet'
        }
        
        if self.config['audit_enabled']:
            self.audit_queue.put(event)
    
    def log_compliance_event(self, event_name: str, compliance_type: str, 
                           status: str, details: Dict[str, Any] = None):
        """Log compliance-related event."""
        severity = AuditSeverity.HIGH if status == 'violation' else AuditSeverity.LOW
        
        event = {
            'timestamp': datetime.now().isoformat(),
            'event_type': AuditEventType.COMPLIANCE.value,
            'event_name': event_name,
            'severity': severity.value,
            'compliance_type': compliance_type,
            'status': status,
            'details': details or {},
            'source': 'hagbes_fleet'
        }
        
        if self.config['audit_enabled']:
            self.audit_queue.put(event)
    
    def generate_audit_report(self, start_date: datetime, end_date: datetime, 
                            event_types: List[str] = None) -> Dict[str, Any]:
        """Generate audit report for specified period."""
        log_dir = Path(self.config['log_directory'])
        
        report = {
            'report_period': {
                'start': start_date.isoformat(),
                'end': end_date.isoformat()
            },
            'summary': {
                'total_events': 0,
                'events_by_type': {},
                'events_by_severity': {},
                'security_incidents': 0,
                'compliance_violations': 0
            },
            'details': {
                'security_events': [],
                'workflow_events': [],
                'access_violations': [],
                'performance_issues': []
            }
        }
        
        # Parse log files for the specified period
        for log_file in log_dir.glob('*.log'):
            try:
                with open(log_file, 'r') as f:
                    for line in f:
                        try:
                            # Parse log entry
                            parts = line.strip().split(' | ', 2)
                            if len(parts) >= 3:
                                timestamp_str = parts[0]
                                level = parts[1]
                                message = parts[2]
                                
                                # Parse timestamp
                                log_time = datetime.fromisoformat(timestamp_str)
                                
                                # Check if within report period
                                if start_date <= log_time <= end_date:
                                    # Try to parse as JSON
                                    try:
                                        event_data = json.loads(message)
                                        self._add_event_to_report(report, event_data, level)
                                    except json.JSONDecodeError:
                                        # Plain text log entry
                                        report['summary']['total_events'] += 1
                        
                        except Exception as e:
                            continue  # Skip malformed log entries
            
            except Exception as e:
                print(f"Error reading log file {log_file}: {e}")
        
        return report
    
    def _add_event_to_report(self, report: Dict[str, Any], event_data: Dict[str, Any], level: str):
        """Add event to audit report."""
        report['summary']['total_events'] += 1
        
        event_type = event_data.get('event_type', 'unknown')
        severity = event_data.get('severity', 'low')
        
        # Count by type
        if event_type not in report['summary']['events_by_type']:
            report['summary']['events_by_type'][event_type] = 0
        report['summary']['events_by_type'][event_type] += 1
        
        # Count by severity
        if severity not in report['summary']['events_by_severity']:
            report['summary']['events_by_severity'][severity] = 0
        report['summary']['events_by_severity'][severity] += 1
        
        # Categorize specific events
        if event_type == AuditEventType.SECURITY.value:
            if severity in ['high', 'critical']:
                report['summary']['security_incidents'] += 1
            report['details']['security_events'].append(event_data)
        
        elif event_type == AuditEventType.WORKFLOW.value:
            report['details']['workflow_events'].append(event_data)
        
        elif event_type == AuditEventType.ACCESS_CONTROL.value:
            if event_data.get('result') == 'denied':
                report['details']['access_violations'].append(event_data)
        
        elif event_type == AuditEventType.PERFORMANCE.value:
            if event_data.get('duration_ms', 0) > 2000:  # > 2 seconds
                report['details']['performance_issues'].append(event_data)
        
        elif event_type == AuditEventType.COMPLIANCE.value:
            if event_data.get('status') == 'violation':
                report['summary']['compliance_violations'] += 1
    
    def cleanup_old_logs(self, retention_days: int = None):
        """Clean up old log files beyond retention period."""
        if retention_days is None:
            retention_days = self.config['retention_days']
        
        cutoff_date = datetime.now() - timedelta(days=retention_days)
        log_dir = Path(self.config['log_directory'])
        
        cleaned_count = 0
        
        for log_file in log_dir.glob('*.log.*'):  # Rotated log files
            try:
                if log_file.stat().st_mtime < cutoff_date.timestamp():
                    log_file.unlink()
                    cleaned_count += 1
            except Exception as e:
                print(f"Error cleaning log file {log_file}: {e}")
        
        return cleaned_count


class AuditContextManager:
    """Context manager for audit logging with performance tracking."""
    
    def __init__(self, audit_logger: FleetAuditLogger, operation_name: str, 
                 user_id: int = None, details: Dict[str, Any] = None):
        self.audit_logger = audit_logger
        self.operation_name = operation_name
        self.user_id = user_id
        self.details = details or {}
        self.start_time = None
    
    def __enter__(self):
        self.start_time = time.time()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        duration_ms = (time.time() - self.start_time) * 1000
        
        if exc_type is None:
            # Operation succeeded
            self.audit_logger.log_performance_event(
                self.operation_name,
                duration_ms,
                self.details
            )
        else:
            # Operation failed
            self.audit_logger.log_security_event(
                f"{self.operation_name}_failed",
                self.user_id or 0,
                {
                    'error_type': exc_type.__name__,
                    'error_message': str(exc_val),
                    'duration_ms': duration_ms,
                    **self.details
                },
                AuditSeverity.HIGH
            )


def main():
    """Main audit system entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description='HAGBES Fleet Audit System')
    parser.add_argument('--config', default='/etc/hagbes_fleet_audit.json',
                       help='Audit configuration file')
    parser.add_argument('--action', choices=['start', 'report', 'cleanup'],
                       default='start', help='Action to perform')
    parser.add_argument('--start-date', help='Report start date (YYYY-MM-DD)')
    parser.add_argument('--end-date', help='Report end date (YYYY-MM-DD)')
    parser.add_argument('--retention-days', type=int, default=365,
                       help='Log retention period in days')
    
    args = parser.parse_args()
    
    # Initialize audit logger
    audit_logger = FleetAuditLogger(args.config)
    
    try:
        if args.action == 'start':
            print("Starting HAGBES Fleet Audit System...")
            # Keep running
            while True:
                time.sleep(60)
        
        elif args.action == 'report':
            if not args.start_date or not args.end_date:
                print("Error: --start-date and --end-date required for report")
                sys.exit(1)
            
            start_date = datetime.fromisoformat(args.start_date)
            end_date = datetime.fromisoformat(args.end_date)
            
            report = audit_logger.generate_audit_report(start_date, end_date)
            print(json.dumps(report, indent=2))
        
        elif args.action == 'cleanup':
            cleaned = audit_logger.cleanup_old_logs(args.retention_days)
            print(f"Cleaned up {cleaned} old log files")
    
    except KeyboardInterrupt:
        print("Shutting down audit system...")
    finally:
        audit_logger.stop_audit_processing()


if __name__ == "__main__":
    main()