# -*- coding: utf-8 -*-
"""
Validation Engine
Stage 1 Core Infrastructure - Passive validation orchestration engine

This module provides the core validation orchestration engine for the
production safeguards system. In Stage 1, it operates in monitor-only
mode without deployment blocking or enforcement.

SAFETY CONSTRAINTS:
- NO deployment blocking
- NO schema mutation
- NO ORM/database writes
- NO enforcement logic
- ALL operations are read-only and passive
- ALL failures must be graceful and non-breaking
"""

import asyncio
import time
import threading
from abc import ABC, abstractmethod
from concurrent.futures import ThreadPoolExecutor, TimeoutError, as_completed
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List, Callable, Union, Type
from enum import Enum
from dataclasses import dataclass, field

from .deployment_config import get_config, is_feature_enabled, FeatureToggle, ValidationThresholds
from .logging_audit_system import get_logger, EventType, Severity, StructuredLogger
from .alert_manager import create_validation_alert, AlertSeverity

_logger = get_logger("validation_engine")


class ValidationStatus(Enum):
    """Validation execution status"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMEOUT = "timeout"
    SKIPPED = "skipped"


class ValidationSeverity(Enum):
    """Validation result severity"""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class ValidationResult:
    """Individual validation result"""
    validator_name: str
    status: ValidationStatus
    severity: ValidationSeverity
    message: str
    details: Dict[str, Any] = field(default_factory=dict)
    execution_time_ms: float = 0.0
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    correlation_id: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert result to dictionary"""
        return {
            'validator_name': self.validator_name,
            'status': self.status.value,
            'severity': self.severity.value,
            'message': self.message,
            'details': self.details,
            'execution_time_ms': self.execution_time_ms,
            'timestamp': self.timestamp.isoformat(),
            'correlation_id': self.correlation_id,
        }


@dataclass
class ValidationSummary:
    """Aggregated validation results"""
    total_validators: int
    completed_validators: int
    failed_validators: int
    skipped_validators: int
    total_execution_time_ms: float
    overall_status: ValidationStatus
    highest_severity: ValidationSeverity
    results: List[ValidationResult] = field(default_factory=list)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    correlation_id: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert summary to dictionary"""
        return {
            'total_validators': self.total_validators,
            'completed_validators': self.completed_validators,
            'failed_validators': self.failed_validators,
            'skipped_validators': self.skipped_validators,
            'total_execution_time_ms': self.total_execution_time_ms,
            'overall_status': self.overall_status.value,
            'highest_severity': self.highest_severity.value,
            'results': [r.to_dict() for r in self.results],
            'timestamp': self.timestamp.isoformat(),
            'correlation_id': self.correlation_id,
        }


class BaseValidator(ABC):
    """
    Base class for all validators.
    
    Provides common interface and safety mechanisms for validation
    components. All validators must be read-only and non-intrusive.
    """
    
    def __init__(self, name: str, description: str = ""):
        """
        Initialize validator.
        
        Args:
            name: Validator name
            description: Validator description
        """
        self.name = name
        self.description = description
        self.logger = get_logger(f"validator_{name}")
        self.enabled = True
        self.timeout_seconds = 60  # Default timeout
    
    @abstractmethod
    def validate(self, context: Dict[str, Any]) -> ValidationResult:
        """
        Perform validation.
        
        Args:
            context: Validation context data
            
        Returns:
            ValidationResult: Validation result
        """
        pass
    
    def is_enabled(self) -> bool:
        """
        Check if validator is enabled.
        
        Returns:
            bool: True if enabled
        """
        return self.enabled and is_feature_enabled(FeatureToggle.MONITOR_MODE)
    
    def set_timeout(self, timeout_seconds: int) -> None:
        """
        Set validation timeout.
        
        Args:
            timeout_seconds: Timeout in seconds
        """
        self.timeout_seconds = max(1, min(timeout_seconds, 300))  # 1-300 seconds
    
    def _create_result(self, status: ValidationStatus, severity: ValidationSeverity,
                      message: str, details: Optional[Dict[str, Any]] = None,
                      execution_time_ms: float = 0.0, correlation_id: Optional[str] = None) -> ValidationResult:
        """
        Create validation result.
        
        Args:
            status: Validation status
            severity: Result severity
            message: Result message
            details: Additional details
            execution_time_ms: Execution time
            correlation_id: Correlation ID
            
        Returns:
            ValidationResult: Created result
        """
        return ValidationResult(
            validator_name=self.name,
            status=status,
            severity=severity,
            message=message,
            details=details or {},
            execution_time_ms=execution_time_ms,
            correlation_id=correlation_id
        )


class MockValidator(BaseValidator):
    """
    Mock validator for Stage 1 testing.
    
    Provides a simple validator implementation for testing the
    validation engine without actual validation logic.
    """
    
    def __init__(self, name: str = "mock_validator", simulate_delay: float = 0.1):
        """
        Initialize mock validator.
        
        Args:
            name: Validator name
            simulate_delay: Simulated execution delay
        """
        super().__init__(name, "Mock validator for testing")
        self.simulate_delay = simulate_delay
    
    def validate(self, context: Dict[str, Any]) -> ValidationResult:
        """
        Perform mock validation.
        
        Args:
            context: Validation context
            
        Returns:
            ValidationResult: Mock validation result
        """
        try:
            start_time = time.time()
            
            # Simulate validation work
            if self.simulate_delay > 0:
                time.sleep(self.simulate_delay)
            
            execution_time = (time.time() - start_time) * 1000
            
            # Mock validation logic
            mock_issue_count = context.get('mock_issue_count', 0)
            
            if mock_issue_count == 0:
                return self._create_result(
                    ValidationStatus.COMPLETED,
                    ValidationSeverity.INFO,
                    "Mock validation passed - no issues found",
                    {'issues_found': 0, 'context_keys': list(context.keys())},
                    execution_time,
                    context.get('correlation_id')
                )
            elif mock_issue_count <= 2:
                return self._create_result(
                    ValidationStatus.COMPLETED,
                    ValidationSeverity.WARNING,
                    f"Mock validation completed with {mock_issue_count} warnings",
                    {'issues_found': mock_issue_count, 'issue_type': 'warning'},
                    execution_time,
                    context.get('correlation_id')
                )
            else:
                return self._create_result(
                    ValidationStatus.COMPLETED,
                    ValidationSeverity.ERROR,
                    f"Mock validation found {mock_issue_count} errors",
                    {'issues_found': mock_issue_count, 'issue_type': 'error'},
                    execution_time,
                    context.get('correlation_id')
                )
                
        except Exception as e:
            return self._create_result(
                ValidationStatus.FAILED,
                ValidationSeverity.ERROR,
                f"Mock validation failed: {e}",
                {'error': str(e)},
                0.0,
                context.get('correlation_id')
            )


class ValidatorRegistry:
    """
    Registry for managing validation components.
    
    Provides plugin-based validator registration and management
    without affecting system operations.
    """
    
    def __init__(self):
        """Initialize validator registry"""
        self.validators: Dict[str, BaseValidator] = {}
        self.logger = get_logger("validator_registry")
        self._initialize_default_validators()
    
    def _initialize_default_validators(self) -> None:
        """Initialize default validators for Stage 1"""
        try:
            # Register mock validator for Stage 1 testing
            self.register_validator(MockValidator("stage1_mock_validator"))
            
            self.logger.log_deployment_event(
                "Default validators initialized",
                severity=Severity.INFO,
                operation="registry_init",
                validator_count=len(self.validators)
            )
            
        except Exception as e:
            self.logger.log_deployment_event(
                f"Default validator initialization failed: {e}",
                severity=Severity.WARNING,
                operation="registry_init"
            )
    
    def register_validator(self, validator: BaseValidator) -> bool:
        """
        Register a validator.
        
        Args:
            validator: Validator to register
            
        Returns:
            bool: True if registered successfully
        """
        try:
            if not isinstance(validator, BaseValidator):
                self.logger.log_deployment_event(
                    f"Invalid validator type: {type(validator)}",
                    severity=Severity.WARNING,
                    validator_name=getattr(validator, 'name', 'unknown')
                )
                return False
            
            self.validators[validator.name] = validator
            
            self.logger.log_deployment_event(
                f"Validator registered: {validator.name}",
                severity=Severity.INFO,
                operation="validator_registration",
                validator_name=validator.name,
                validator_description=validator.description
            )
            
            return True
            
        except Exception as e:
            self.logger.log_deployment_event(
                f"Validator registration failed: {e}",
                severity=Severity.ERROR,
                validator_name=getattr(validator, 'name', 'unknown')
            )
            return False
    
    def unregister_validator(self, name: str) -> bool:
        """
        Unregister a validator.
        
        Args:
            name: Validator name to unregister
            
        Returns:
            bool: True if unregistered successfully
        """
        try:
            if name in self.validators:
                del self.validators[name]
                self.logger.log_deployment_event(
                    f"Validator unregistered: {name}",
                    severity=Severity.INFO,
                    operation="validator_unregistration",
                    validator_name=name
                )
                return True
            else:
                self.logger.log_deployment_event(
                    f"Validator not found for unregistration: {name}",
                    severity=Severity.WARNING,
                    validator_name=name
                )
                return False
                
        except Exception as e:
            self.logger.log_deployment_event(
                f"Validator unregistration failed: {e}",
                severity=Severity.ERROR,
                validator_name=name
            )
            return False
    
    def get_validator(self, name: str) -> Optional[BaseValidator]:
        """
        Get validator by name.
        
        Args:
            name: Validator name
            
        Returns:
            Optional[BaseValidator]: Validator if found
        """
        return self.validators.get(name)
    
    def get_enabled_validators(self) -> List[BaseValidator]:
        """
        Get list of enabled validators.
        
        Returns:
            List[BaseValidator]: List of enabled validators
        """
        try:
            return [v for v in self.validators.values() if v.is_enabled()]
        except Exception as e:
            self.logger.log_deployment_event(
                f"Enabled validators retrieval failed: {e}",
                severity=Severity.WARNING
            )
            return []
    
    def get_validator_info(self) -> Dict[str, Dict[str, Any]]:
        """
        Get information about all registered validators.
        
        Returns:
            Dict[str, Dict[str, Any]]: Validator information
        """
        try:
            info = {}
            for name, validator in self.validators.items():
                info[name] = {
                    'name': validator.name,
                    'description': validator.description,
                    'enabled': validator.is_enabled(),
                    'timeout_seconds': validator.timeout_seconds,
                }
            return info
        except Exception as e:
            self.logger.log_deployment_event(
                f"Validator info retrieval failed: {e}",
                severity=Severity.WARNING
            )
            return {}


class ValidationEngine:
    """
    Core validation orchestration engine.
    
    Provides parallel validation execution, timeout handling,
    result aggregation, and async-safe execution without
    affecting system operations.
    
    SAFETY: All operations are read-only and non-intrusive.
    """
    
    def __init__(self, max_workers: int = 4):
        """
        Initialize validation engine.
        
        Args:
            max_workers: Maximum number of worker threads
        """
        self.registry = ValidatorRegistry()
        self.logger = get_logger("validation_engine")
        self.max_workers = max_workers
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        self._shutdown = False
    
    def _execute_validator_with_timeout(self, validator: BaseValidator, 
                                      context: Dict[str, Any]) -> ValidationResult:
        """
        Execute validator with timeout handling.
        
        Args:
            validator: Validator to execute
            context: Validation context
            
        Returns:
            ValidationResult: Validation result
        """
        try:
            start_time = time.time()
            
            # Submit validation task
            future = self.executor.submit(validator.validate, context)
            
            try:
                # Wait for result with timeout
                result = future.result(timeout=validator.timeout_seconds)
                execution_time = (time.time() - start_time) * 1000
                result.execution_time_ms = execution_time
                return result
                
            except TimeoutError:
                # Cancel the future if possible
                future.cancel()
                execution_time = (time.time() - start_time) * 1000
                
                return validator._create_result(
                    ValidationStatus.TIMEOUT,
                    ValidationSeverity.WARNING,
                    f"Validation timed out after {validator.timeout_seconds} seconds",
                    {'timeout_seconds': validator.timeout_seconds},
                    execution_time,
                    context.get('correlation_id')
                )
                
        except Exception as e:
            execution_time = (time.time() - start_time) * 1000 if 'start_time' in locals() else 0.0
            
            return validator._create_result(
                ValidationStatus.FAILED,
                ValidationSeverity.ERROR,
                f"Validation execution failed: {e}",
                {'error': str(e), 'error_type': type(e).__name__},
                execution_time,
                context.get('correlation_id')
            )
    
    def _aggregate_results(self, results: List[ValidationResult], 
                          correlation_id: Optional[str] = None) -> ValidationSummary:
        """
        Aggregate validation results into summary.
        
        Args:
            results: List of validation results
            correlation_id: Correlation ID
            
        Returns:
            ValidationSummary: Aggregated summary
        """
        try:
            total_validators = len(results)
            completed_validators = len([r for r in results if r.status == ValidationStatus.COMPLETED])
            failed_validators = len([r for r in results if r.status == ValidationStatus.FAILED])
            skipped_validators = len([r for r in results if r.status == ValidationStatus.SKIPPED])
            total_execution_time = sum(r.execution_time_ms for r in results)
            
            # Determine overall status
            if failed_validators > 0:
                overall_status = ValidationStatus.FAILED
            elif any(r.status == ValidationStatus.TIMEOUT for r in results):
                overall_status = ValidationStatus.TIMEOUT
            elif completed_validators == total_validators:
                overall_status = ValidationStatus.COMPLETED
            else:
                overall_status = ValidationStatus.FAILED
            
            # Determine highest severity
            severity_order = [ValidationSeverity.INFO, ValidationSeverity.WARNING, 
                            ValidationSeverity.ERROR, ValidationSeverity.CRITICAL]
            highest_severity = ValidationSeverity.INFO
            
            for result in results:
                if severity_order.index(result.severity) > severity_order.index(highest_severity):
                    highest_severity = result.severity
            
            return ValidationSummary(
                total_validators=total_validators,
                completed_validators=completed_validators,
                failed_validators=failed_validators,
                skipped_validators=skipped_validators,
                total_execution_time_ms=total_execution_time,
                overall_status=overall_status,
                highest_severity=highest_severity,
                results=results,
                correlation_id=correlation_id
            )
            
        except Exception as e:
            self.logger.log_validation_event(
                f"Result aggregation failed: {e}",
                severity=Severity.ERROR,
                validation_type="aggregation"
            )
            
            # Return minimal summary on error
            return ValidationSummary(
                total_validators=len(results),
                completed_validators=0,
                failed_validators=len(results),
                skipped_validators=0,
                total_execution_time_ms=0.0,
                overall_status=ValidationStatus.FAILED,
                highest_severity=ValidationSeverity.ERROR,
                results=results,
                correlation_id=correlation_id
            )
    
    def execute_validation(self, context: Dict[str, Any], 
                          validator_names: Optional[List[str]] = None,
                          correlation_id: Optional[str] = None) -> ValidationSummary:
        """
        Execute validation with specified validators.
        
        Args:
            context: Validation context data
            validator_names: Specific validators to run (None for all enabled)
            correlation_id: Correlation ID for tracking
            
        Returns:
            ValidationSummary: Validation results summary
        """
        try:
            start_time = time.time()
            
            # Get validators to execute
            if validator_names:
                validators = []
                for name in validator_names:
                    validator = self.registry.get_validator(name)
                    if validator and validator.is_enabled():
                        validators.append(validator)
                    elif validator:
                        self.logger.log_validation_event(
                            f"Validator disabled, skipping: {name}",
                            severity=Severity.INFO,
                            validation_type="execution",
                            validator_name=name
                        )
            else:
                validators = self.registry.get_enabled_validators()
            
            if not validators:
                self.logger.log_validation_event(
                    "No enabled validators found",
                    severity=Severity.WARNING,
                    validation_type="execution"
                )
                return ValidationSummary(
                    total_validators=0,
                    completed_validators=0,
                    failed_validators=0,
                    skipped_validators=0,
                    total_execution_time_ms=0.0,
                    overall_status=ValidationStatus.SKIPPED,
                    highest_severity=ValidationSeverity.INFO,
                    correlation_id=correlation_id
                )
            
            # Log validation start
            self.logger.log_validation_event(
                f"Starting validation with {len(validators)} validators",
                severity=Severity.INFO,
                validation_type="execution",
                validator_count=len(validators),
                validator_names=[v.name for v in validators]
            )
            
            # Execute validators in parallel
            results = []
            futures = {}
            
            for validator in validators:
                try:
                    future = self.executor.submit(
                        self._execute_validator_with_timeout,
                        validator,
                        context
                    )
                    futures[future] = validator
                except Exception as e:
                    # Create failed result for submission error
                    result = validator._create_result(
                        ValidationStatus.FAILED,
                        ValidationSeverity.ERROR,
                        f"Validator submission failed: {e}",
                        {'error': str(e)},
                        0.0,
                        correlation_id
                    )
                    results.append(result)
            
            # Collect results as they complete
            for future in as_completed(futures, timeout=300):  # 5 minute overall timeout
                try:
                    result = future.result()
                    results.append(result)
                except Exception as e:
                    validator = futures[future]
                    result = validator._create_result(
                        ValidationStatus.FAILED,
                        ValidationSeverity.ERROR,
                        f"Validator result collection failed: {e}",
                        {'error': str(e)},
                        0.0,
                        correlation_id
                    )
                    results.append(result)
            
            # Aggregate results
            summary = self._aggregate_results(results, correlation_id)
            
            # Log completion
            execution_time = (time.time() - start_time) * 1000
            self.logger.log_validation_event(
                f"Validation completed in {execution_time:.2f}ms",
                severity=Severity.INFO,
                validation_type="execution",
                result=summary.to_dict()
            )
            
            # Create alerts for significant issues
            self._process_validation_alerts(summary)
            
            return summary
            
        except Exception as e:
            self.logger.log_validation_event(
                f"Validation execution failed: {e}",
                severity=Severity.ERROR,
                validation_type="execution"
            )
            
            # Return error summary
            return ValidationSummary(
                total_validators=0,
                completed_validators=0,
                failed_validators=1,
                skipped_validators=0,
                total_execution_time_ms=0.0,
                overall_status=ValidationStatus.FAILED,
                highest_severity=ValidationSeverity.ERROR,
                correlation_id=correlation_id
            )
    
    def _process_validation_alerts(self, summary: ValidationSummary) -> None:
        """
        Process validation results and create alerts as needed.
        
        Args:
            summary: Validation summary to process
        """
        try:
            # Create alerts for failed validations
            if summary.failed_validators > 0:
                create_validation_alert(
                    title=f"Validation Failures Detected",
                    message=f"{summary.failed_validators} out of {summary.total_validators} validators failed",
                    severity=AlertSeverity.MEDIUM,
                    correlation_id=summary.correlation_id,
                    failed_count=summary.failed_validators,
                    total_count=summary.total_validators
                )
            
            # Create alerts for critical severity results
            critical_results = [r for r in summary.results if r.severity == ValidationSeverity.CRITICAL]
            if critical_results:
                create_validation_alert(
                    title="Critical Validation Issues",
                    message=f"{len(critical_results)} critical validation issues detected",
                    severity=AlertSeverity.HIGH,
                    correlation_id=summary.correlation_id,
                    critical_issues=[r.message for r in critical_results]
                )
            
        except Exception as e:
            self.logger.log_validation_event(
                f"Validation alert processing failed: {e}",
                severity=Severity.WARNING,
                validation_type="alert_processing"
            )
    
    def get_validation_status(self) -> Dict[str, Any]:
        """
        Get current validation engine status.
        
        Returns:
            Dict[str, Any]: Engine status information
        """
        try:
            validator_info = self.registry.get_validator_info()
            enabled_count = len([v for v in validator_info.values() if v['enabled']])
            
            return {
                'engine_active': not self._shutdown,
                'max_workers': self.max_workers,
                'total_validators': len(validator_info),
                'enabled_validators': enabled_count,
                'monitor_mode': is_feature_enabled(FeatureToggle.MONITOR_MODE),
                'enforcement_mode': is_feature_enabled(FeatureToggle.ENFORCEMENT_MODE),
                'validators': validator_info,
            }
            
        except Exception as e:
            self.logger.log_validation_event(
                f"Validation status retrieval failed: {e}",
                severity=Severity.WARNING
            )
            return {
                'engine_active': False,
                'error': str(e)
            }
    
    def shutdown(self) -> None:
        """Shutdown validation engine gracefully"""
        try:
            self._shutdown = True
            self.executor.shutdown(wait=True)
            
            self.logger.log_deployment_event(
                "Validation engine shutdown completed",
                severity=Severity.INFO,
                operation="engine_shutdown"
            )
            
        except Exception as e:
            self.logger.log_deployment_event(
                f"Validation engine shutdown failed: {e}",
                severity=Severity.WARNING,
                operation="engine_shutdown"
            )


# Global validation engine instance
validation_engine = ValidationEngine()


def execute_validation(context: Dict[str, Any], validator_names: Optional[List[str]] = None,
                      correlation_id: Optional[str] = None) -> ValidationSummary:
    """
    Execute validation globally.
    
    Args:
        context: Validation context
        validator_names: Specific validators to run
        correlation_id: Correlation ID
        
    Returns:
        ValidationSummary: Validation results
    """
    return validation_engine.execute_validation(context, validator_names, correlation_id)


def register_validator(validator: BaseValidator) -> bool:
    """
    Register validator globally.
    
    Args:
        validator: Validator to register
        
    Returns:
        bool: True if registered successfully
    """
    return validation_engine.registry.register_validator(validator)


def get_validation_status() -> Dict[str, Any]:
    """
    Get validation engine status globally.
    
    Returns:
        Dict[str, Any]: Engine status
    """
    return validation_engine.get_validation_status()