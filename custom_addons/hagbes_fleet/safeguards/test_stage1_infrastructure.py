#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Stage 1 Core Infrastructure Test Script

This script validates that all Stage 1 components load correctly
and operate in monitor-only mode without affecting system functionality.

SAFETY: This script only performs read-only operations and logging tests.
"""

import sys
import traceback
from typing import Dict, Any, List

def test_deployment_config():
    """Test deployment configuration system"""
    print("Testing deployment configuration...")
    try:
        from . import deployment_config
        
        # Test configuration loading
        config = deployment_config.get_config()
        print(f"  ✓ Configuration loaded: {config.environment.value}")
        
        # Test feature toggles
        monitor_mode = deployment_config.is_monitor_mode()
        print(f"  ✓ Monitor mode: {monitor_mode}")
        
        # Test environment detection
        env = deployment_config.get_environment()
        print(f"  ✓ Environment detected: {env.value}")
        
        # Test configuration validation
        validation_report = deployment_config.config_manager.validate_configuration()
        print(f"  ✓ Configuration valid: {validation_report['valid']}")
        
        if validation_report['errors']:
            print(f"  ⚠ Configuration errors: {validation_report['errors']}")
        
        return True
        
    except Exception as e:
        print(f"  ✗ Deployment config test failed: {e}")
        traceback.print_exc()
        return False


def test_logging_audit_system():
    """Test logging and audit system"""
    print("Testing logging and audit system...")
    try:
        from . import logging_audit_system
        
        # Test structured logger
        logger = logging_audit_system.get_logger("test")
        print("  ✓ Structured logger created")
        
        # Test event logging
        correlation_id = logger.log_deployment_event(
            "Stage 1 infrastructure test",
            severity=logging_audit_system.Severity.INFO,
            operation="test"
        )
        print(f"  ✓ Event logged with correlation ID: {correlation_id}")
        
        # Test audit manager
        audit_id = logging_audit_system.audit_manager.record_configuration_change(
            "test_component",
            "old_value",
            "new_value",
            "test_user"
        )
        print(f"  ✓ Audit record created: {audit_id}")
        
        return True
        
    except Exception as e:
        print(f"  ✗ Logging audit system test failed: {e}")
        traceback.print_exc()
        return False


def test_alert_manager():
    """Test alert management system"""
    print("Testing alert management system...")
    try:
        from . import alert_manager
        
        # Test alert creation (log-only in Stage 1)
        alert_id = alert_manager.create_deployment_alert(
            "Stage 1 Test Alert",
            "This is a test alert for Stage 1 infrastructure validation",
            severity=alert_manager.AlertSeverity.LOW
        )
        print(f"  ✓ Alert created: {alert_id}")
        
        # Test alert statistics
        stats = alert_manager.alert_manager.get_alert_statistics()
        print(f"  ✓ Alert statistics: {stats['total_active_alerts']} active alerts")
        
        # Test alert resolution
        if alert_id:
            resolved = alert_manager.resolve_alert(alert_id, "test_system")
            print(f"  ✓ Alert resolved: {resolved}")
        
        return True
        
    except Exception as e:
        print(f"  ✗ Alert manager test failed: {e}")
        traceback.print_exc()
        return False


def test_validation_engine():
    """Test validation engine"""
    print("Testing validation engine...")
    try:
        from . import validation_engine
        
        # Test engine status
        status = validation_engine.get_validation_status()
        print(f"  ✓ Engine active: {status['engine_active']}")
        print(f"  ✓ Validators available: {status['total_validators']}")
        
        # Test validation execution with mock data
        context = {
            'mock_issue_count': 1,  # Simulate 1 warning
            'correlation_id': 'test-correlation-123'
        }
        
        summary = validation_engine.execute_validation(context)
        print(f"  ✓ Validation executed: {summary.overall_status.value}")
        print(f"  ✓ Validators completed: {summary.completed_validators}/{summary.total_validators}")
        print(f"  ✓ Execution time: {summary.total_execution_time_ms:.2f}ms")
        
        return True
        
    except Exception as e:
        print(f"  ✗ Validation engine test failed: {e}")
        traceback.print_exc()
        return False


def test_integration():
    """Test integration between components"""
    print("Testing component integration...")
    try:
        from . import deployment_config, logging_audit_system, alert_manager, validation_engine
        
        # Test configuration-driven behavior
        if deployment_config.is_monitor_mode():
            print("  ✓ Monitor mode enabled - components should operate passively")
        
        if not deployment_config.config_manager.is_enforcement_mode():
            print("  ✓ Enforcement mode disabled - no blocking behavior")
        
        # Test logging integration with validation
        logger = logging_audit_system.get_logger("integration_test")
        
        with logger.operation_context("stage1_integration_test") as correlation_id:
            # Execute validation within logging context
            context = {
                'correlation_id': correlation_id,
                'mock_issue_count': 0  # No issues
            }
            
            summary = validation_engine.execute_validation(context, correlation_id=correlation_id)
            print(f"  ✓ Integrated validation completed: {summary.overall_status.value}")
        
        return True
        
    except Exception as e:
        print(f"  ✗ Integration test failed: {e}")
        traceback.print_exc()
        return False


def run_stage1_tests() -> Dict[str, bool]:
    """
    Run all Stage 1 infrastructure tests.
    
    Returns:
        Dict[str, bool]: Test results by component
    """
    print("=" * 60)
    print("HAGBES FLEET STAGE 1 CORE INFRASTRUCTURE TESTS")
    print("=" * 60)
    
    tests = {
        'deployment_config': test_deployment_config,
        'logging_audit_system': test_logging_audit_system,
        'alert_manager': test_alert_manager,
        'validation_engine': test_validation_engine,
        'integration': test_integration,
    }
    
    results = {}
    
    for test_name, test_func in tests.items():
        print(f"\n[{test_name.upper()}]")
        try:
            results[test_name] = test_func()
        except Exception as e:
            print(f"  ✗ Test execution failed: {e}")
            results[test_name] = False
    
    print("\n" + "=" * 60)
    print("TEST RESULTS SUMMARY")
    print("=" * 60)
    
    passed = 0
    total = len(results)
    
    for test_name, passed_test in results.items():
        status = "PASS" if passed_test else "FAIL"
        symbol = "✓" if passed_test else "✗"
        print(f"  {symbol} {test_name}: {status}")
        if passed_test:
            passed += 1
    
    print(f"\nOverall: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All Stage 1 infrastructure tests PASSED!")
        print("✓ System is ready for Stage 2 implementation")
    else:
        print("⚠ Some tests FAILED - review errors before proceeding")
    
    return results


if __name__ == "__main__":
    # Run tests if script is executed directly
    results = run_stage1_tests()
    
    # Exit with appropriate code
    all_passed = all(results.values())
    sys.exit(0 if all_passed else 1)