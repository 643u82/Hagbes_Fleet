#!/usr/bin/env python3
"""
HAGBES FLEET RUNTIME MONITORING SYSTEM
======================================

Enterprise runtime health monitoring for fleet workflows that detects
and alerts on production issues before they impact users.

Monitors:
- Failed approval transitions
- Access control violations  
- RPC_ERROR frequency
- Failed scheduled actions
- Invalid state transitions
- Missing dependency modules
"""

import logging
import json
import time
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from pathlib import Path
import threading
import queue
import smtplib
from email.mime.text import MimeText
from email.mime.multipart import MimeMultipart

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class FleetRuntimeMonitor:
    """Runtime health monitoring system for hagbes_fleet module."""
    
    def __init__(self, config_path: str):
        self.config_path = Path(config_path)
        self.config = self._load_config()
        self.metrics = {
            'approval_failures': [],
            'access_violations': [],
            'rpc_errors': [],
            'scheduled_action_failures': [],
            'invalid_state_transitions': [],
            'dependency_issues': [],
            'performance_metrics': {}
        }
        self.alert_queue = queue.Queue()
        self.monitoring_active = False
        self.alert_thread = None
    
    def _load_config(self) -> Dict[str, Any]:
        """Load monitoring configuration."""
        default_config = {
            'monitoring_enabled': True,
            'alert_thresholds': {
                'approval_failure_rate': 0.05,  # 5% failure rate
                'rpc_error_rate': 0.02,         # 2% error rate
                'access_violation_count': 10,    # 10 violations per hour
                'state_transition_errors': 5     # 5 errors per hour
            },
            'alert_channels': {
                'email': {
                    'enabled': True,
                    'smtp_server': 'localhost',
                    'smtp_port': 587,
                    'recipients': ['admin@company.com']
                },
                'log': {
                    'enabled': True,
                    'log_file': '/var/log/hagbes_fleet_monitor.log'
                }
            },
            'monitoring_intervals': {
                'metrics_collection': 60,    # seconds
                'alert_evaluation': 300,     # seconds
                'report_generation': 3600    # seconds
            }
        }
        
        if self.config_path.exists():
            try:
                with open(self.config_path, 'r') as f:
                    user_config = json.load(f)
                default_config.update(user_config)
            except Exception as e:
                logger.warning(f"Could not load config from {self.config_path}: {e}")
        
        return default_config
    
    def start_monitoring(self):
        """Start the runtime monitoring system."""
        if self.monitoring_active:
            logger.warning("Monitoring is already active")
            return
        
        logger.info("🚀 Starting HAGBES Fleet runtime monitoring...")
        self.monitoring_active = True
        
        # Start alert processing thread
        self.alert_thread = threading.Thread(target=self._process_alerts, daemon=True)
        self.alert_thread.start()
        
        # Start monitoring threads
        threading.Thread(target=self._monitor_approval_workflows, daemon=True).start()
        threading.Thread(target=self._monitor_access_control, daemon=True).start()
        threading.Thread(target=self._monitor_rpc_errors, daemon=True).start()
        threading.Thread(target=self._monitor_scheduled_actions, daemon=True).start()
        threading.Thread(target=self._monitor_state_transitions, daemon=True).start()
        
        logger.info("✅ Runtime monitoring system started")
    
    def stop_monitoring(self):
        """Stop the runtime monitoring system."""
        logger.info("🛑 Stopping runtime monitoring...")
        self.monitoring_active = False
        
        if self.alert_thread:
            self.alert_thread.join(timeout=5)
        
        logger.info("✅ Runtime monitoring stopped")
    
    def _monitor_approval_workflows(self):
        """Monitor approval workflow failures."""
        logger.info("📊 Starting approval workflow monitoring...")
        
        while self.monitoring_active:
            try:
                # Simulate monitoring approval workflow health
                # In real implementation, this would query the database
                approval_metrics = self._collect_approval_metrics()
                
                failure_rate = approval_metrics.get('failure_rate', 0)
                threshold = self.config['alert_thresholds']['approval_failure_rate']
                
                if failure_rate > threshold:
                    alert = {
                        'type': 'approval_workflow_failure',
                        'severity': 'high',
                        'message': f"Approval workflow failure rate ({failure_rate:.2%}) exceeds threshold ({threshold:.2%})",
                        'metrics': approval_metrics,
                        'timestamp': datetime.now().isoformat()
                    }
                    self.alert_queue.put(alert)
                
                self.metrics['approval_failures'].append({
                    'timestamp': datetime.now().isoformat(),
                    'failure_rate': failure_rate,
                    'total_approvals': approval_metrics.get('total_approvals', 0),
                    'failed_approvals': approval_metrics.get('failed_approvals', 0)
                })
                
                # Keep only last 24 hours of metrics
                cutoff = datetime.now() - timedelta(hours=24)
                self.metrics['approval_failures'] = [
                    m for m in self.metrics['approval_failures']
                    if datetime.fromisoformat(m['timestamp']) > cutoff
                ]
                
            except Exception as e:
                logger.error(f"Error in approval workflow monitoring: {e}")
            
            time.sleep(self.config['monitoring_intervals']['metrics_collection'])
    
    def _monitor_access_control(self):
        """Monitor access control violations."""
        logger.info("🔒 Starting access control monitoring...")
        
        while self.monitoring_active:
            try:
                # Monitor access control violations
                violations = self._collect_access_violations()
                
                violation_count = len(violations)
                threshold = self.config['alert_thresholds']['access_violation_count']
                
                if violation_count > threshold:
                    alert = {
                        'type': 'access_control_violation',
                        'severity': 'critical',
                        'message': f"Access control violations ({violation_count}) exceed threshold ({threshold})",
                        'violations': violations,
                        'timestamp': datetime.now().isoformat()
                    }
                    self.alert_queue.put(alert)
                
                self.metrics['access_violations'].extend(violations)
                
                # Keep only last 24 hours of violations
                cutoff = datetime.now() - timedelta(hours=24)
                self.metrics['access_violations'] = [
                    v for v in self.metrics['access_violations']
                    if datetime.fromisoformat(v['timestamp']) > cutoff
                ]
                
            except Exception as e:
                logger.error(f"Error in access control monitoring: {e}")
            
            time.sleep(self.config['monitoring_intervals']['metrics_collection'])
    
    def _monitor_rpc_errors(self):
        """Monitor RPC error frequency."""
        logger.info("🌐 Starting RPC error monitoring...")
        
        while self.monitoring_active:
            try:
                # Monitor RPC errors
                rpc_metrics = self._collect_rpc_metrics()
                
                error_rate = rpc_metrics.get('error_rate', 0)
                threshold = self.config['alert_thresholds']['rpc_error_rate']
                
                if error_rate > threshold:
                    alert = {
                        'type': 'rpc_error_spike',
                        'severity': 'medium',
                        'message': f"RPC error rate ({error_rate:.2%}) exceeds threshold ({threshold:.2%})",
                        'metrics': rpc_metrics,
                        'timestamp': datetime.now().isoformat()
                    }
                    self.alert_queue.put(alert)
                
                self.metrics['rpc_errors'].append({
                    'timestamp': datetime.now().isoformat(),
                    'error_rate': error_rate,
                    'total_requests': rpc_metrics.get('total_requests', 0),
                    'error_count': rpc_metrics.get('error_count', 0)
                })
                
                # Keep only last 24 hours of metrics
                cutoff = datetime.now() - timedelta(hours=24)
                self.metrics['rpc_errors'] = [
                    m for m in self.metrics['rpc_errors']
                    if datetime.fromisoformat(m['timestamp']) > cutoff
                ]
                
            except Exception as e:
                logger.error(f"Error in RPC monitoring: {e}")
            
            time.sleep(self.config['monitoring_intervals']['metrics_collection'])
    
    def _monitor_scheduled_actions(self):
        """Monitor scheduled action failures."""
        logger.info("⏰ Starting scheduled action monitoring...")
        
        while self.monitoring_active:
            try:
                # Monitor scheduled actions (cron jobs)
                failed_actions = self._collect_failed_scheduled_actions()
                
                if failed_actions:
                    alert = {
                        'type': 'scheduled_action_failure',
                        'severity': 'medium',
                        'message': f"Scheduled actions failed: {len(failed_actions)} actions",
                        'failed_actions': failed_actions,
                        'timestamp': datetime.now().isoformat()
                    }
                    self.alert_queue.put(alert)
                
                self.metrics['scheduled_action_failures'].extend(failed_actions)
                
                # Keep only last 24 hours of failures
                cutoff = datetime.now() - timedelta(hours=24)
                self.metrics['scheduled_action_failures'] = [
                    f for f in self.metrics['scheduled_action_failures']
                    if datetime.fromisoformat(f['timestamp']) > cutoff
                ]
                
            except Exception as e:
                logger.error(f"Error in scheduled action monitoring: {e}")
            
            time.sleep(self.config['monitoring_intervals']['metrics_collection'])
    
    def _monitor_state_transitions(self):
        """Monitor invalid state transitions."""
        logger.info("🔄 Starting state transition monitoring...")
        
        while self.monitoring_active:
            try:
                # Monitor invalid state transitions
                invalid_transitions = self._collect_invalid_state_transitions()
                
                transition_count = len(invalid_transitions)
                threshold = self.config['alert_thresholds']['state_transition_errors']
                
                if transition_count > threshold:
                    alert = {
                        'type': 'invalid_state_transition',
                        'severity': 'high',
                        'message': f"Invalid state transitions ({transition_count}) exceed threshold ({threshold})",
                        'transitions': invalid_transitions,
                        'timestamp': datetime.now().isoformat()
                    }
                    self.alert_queue.put(alert)
                
                self.metrics['invalid_state_transitions'].extend(invalid_transitions)
                
                # Keep only last 24 hours of transitions
                cutoff = datetime.now() - timedelta(hours=24)
                self.metrics['invalid_state_transitions'] = [
                    t for t in self.metrics['invalid_state_transitions']
                    if datetime.fromisoformat(t['timestamp']) > cutoff
                ]
                
            except Exception as e:
                logger.error(f"Error in state transition monitoring: {e}")
            
            time.sleep(self.config['monitoring_intervals']['metrics_collection'])
    
    def _collect_approval_metrics(self) -> Dict[str, Any]:
        """Collect approval workflow metrics."""
        # In real implementation, this would query the database
        # For now, return simulated metrics
        return {
            'total_approvals': 100,
            'failed_approvals': 2,
            'failure_rate': 0.02,
            'avg_approval_time': 3600,  # seconds
            'pending_approvals': 15
        }
    
    def _collect_access_violations(self) -> List[Dict[str, Any]]:
        """Collect access control violations."""
        # In real implementation, this would check security logs
        # For now, return simulated violations
        return []
    
    def _collect_rpc_metrics(self) -> Dict[str, Any]:
        """Collect RPC error metrics."""
        # In real implementation, this would check server logs
        return {
            'total_requests': 1000,
            'error_count': 5,
            'error_rate': 0.005,
            'avg_response_time': 250  # milliseconds
        }
    
    def _collect_failed_scheduled_actions(self) -> List[Dict[str, Any]]:
        """Collect failed scheduled actions."""
        # In real implementation, this would check ir.cron logs
        return []
    
    def _collect_invalid_state_transitions(self) -> List[Dict[str, Any]]:
        """Collect invalid state transitions."""
        # In real implementation, this would check audit logs
        return []
    
    def _process_alerts(self):
        """Process alerts from the alert queue."""
        logger.info("📢 Starting alert processing...")
        
        while self.monitoring_active:
            try:
                # Wait for alerts with timeout
                alert = self.alert_queue.get(timeout=1)
                
                # Process the alert
                self._send_alert(alert)
                
                # Mark task as done
                self.alert_queue.task_done()
                
            except queue.Empty:
                continue
            except Exception as e:
                logger.error(f"Error processing alert: {e}")
    
    def _send_alert(self, alert: Dict[str, Any]):
        """Send alert through configured channels."""
        logger.warning(f"🚨 ALERT: {alert['message']}")
        
        # Log alert
        if self.config['alert_channels']['log']['enabled']:
            self._log_alert(alert)
        
        # Send email alert
        if self.config['alert_channels']['email']['enabled']:
            self._send_email_alert(alert)
    
    def _log_alert(self, alert: Dict[str, Any]):
        """Log alert to file."""
        try:
            log_file = self.config['alert_channels']['log']['log_file']
            with open(log_file, 'a') as f:
                f.write(f"{alert['timestamp']} - {alert['severity'].upper()} - {alert['message']}\n")
        except Exception as e:
            logger.error(f"Failed to log alert: {e}")
    
    def _send_email_alert(self, alert: Dict[str, Any]):
        """Send email alert."""
        try:
            email_config = self.config['alert_channels']['email']
            
            msg = MimeMultipart()
            msg['From'] = 'hagbes-fleet-monitor@company.com'
            msg['To'] = ', '.join(email_config['recipients'])
            msg['Subject'] = f"HAGBES Fleet Alert: {alert['type']}"
            
            body = f"""
HAGBES Fleet Monitoring Alert

Type: {alert['type']}
Severity: {alert['severity']}
Timestamp: {alert['timestamp']}

Message: {alert['message']}

Details:
{json.dumps(alert, indent=2)}
            """
            
            msg.attach(MimeText(body, 'plain'))
            
            server = smtplib.SMTP(email_config['smtp_server'], email_config['smtp_port'])
            server.send_message(msg)
            server.quit()
            
        except Exception as e:
            logger.error(f"Failed to send email alert: {e}")
    
    def generate_health_report(self) -> Dict[str, Any]:
        """Generate comprehensive health report."""
        logger.info("📊 Generating health report...")
        
        report = {
            'timestamp': datetime.now().isoformat(),
            'monitoring_status': 'active' if self.monitoring_active else 'inactive',
            'metrics_summary': {
                'approval_failures_24h': len(self.metrics['approval_failures']),
                'access_violations_24h': len(self.metrics['access_violations']),
                'rpc_errors_24h': len(self.metrics['rpc_errors']),
                'scheduled_action_failures_24h': len(self.metrics['scheduled_action_failures']),
                'invalid_state_transitions_24h': len(self.metrics['invalid_state_transitions'])
            },
            'health_status': self._calculate_health_status(),
            'recommendations': self._generate_recommendations()
        }
        
        # Save report
        report_path = Path('/tmp/hagbes_fleet_health_report.json')
        with open(report_path, 'w') as f:
            json.dump(report, f, indent=2)
        
        logger.info(f"Health report saved to {report_path}")
        return report
    
    def _calculate_health_status(self) -> str:
        """Calculate overall system health status."""
        metrics = self.metrics
        
        # Count recent issues
        recent_issues = (
            len(metrics['approval_failures']) +
            len(metrics['access_violations']) +
            len(metrics['rpc_errors']) +
            len(metrics['scheduled_action_failures']) +
            len(metrics['invalid_state_transitions'])
        )
        
        if recent_issues == 0:
            return 'excellent'
        elif recent_issues < 10:
            return 'good'
        elif recent_issues < 50:
            return 'warning'
        else:
            return 'critical'
    
    def _generate_recommendations(self) -> List[str]:
        """Generate health improvement recommendations."""
        recommendations = []
        
        if len(self.metrics['approval_failures']) > 10:
            recommendations.append("Review approval workflow configuration for frequent failures")
        
        if len(self.metrics['access_violations']) > 5:
            recommendations.append("Audit user permissions and security group assignments")
        
        if len(self.metrics['rpc_errors']) > 20:
            recommendations.append("Investigate RPC error patterns and server performance")
        
        if len(self.metrics['invalid_state_transitions']) > 5:
            recommendations.append("Review state transition logic and validation rules")
        
        if not recommendations:
            recommendations.append("System health is good - continue monitoring")
        
        return recommendations


def main():
    """Main monitoring entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description='HAGBES Fleet Runtime Monitor')
    parser.add_argument('--config', default='/etc/hagbes_fleet_monitor.json',
                       help='Configuration file path')
    parser.add_argument('--daemon', action='store_true',
                       help='Run as daemon')
    
    args = parser.parse_args()
    
    monitor = FleetRuntimeMonitor(args.config)
    
    try:
        monitor.start_monitoring()
        
        if args.daemon:
            # Run as daemon
            while True:
                time.sleep(3600)  # Sleep for 1 hour
                monitor.generate_health_report()
        else:
            # Run for a short time and generate report
            time.sleep(60)
            report = monitor.generate_health_report()
            print(json.dumps(report, indent=2))
    
    except KeyboardInterrupt:
        logger.info("Received interrupt signal")
    finally:
        monitor.stop_monitoring()


if __name__ == "__main__":
    main()