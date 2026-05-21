# -*- coding: utf-8 -*-
"""
Deployment Configuration Management System
Stage 1 Core Infrastructure - Non-intrusive configuration management

This module provides centralized configuration management for the production
safeguards system. It handles environment detection, feature toggles, and
threshold configuration without affecting existing fleet functionality.

SAFETY CONSTRAINTS:
- NO enforcement logic
- NO deployment blocking
- NO database operations
- NO ORM modifications
- ALL failures must be graceful and non-breaking
"""

import os
import logging
from typing import Dict, Any, Optional, Union
from dataclasses import dataclass, field
from enum import Enum

_logger = logging.getLogger(__name__)


class Environment(Enum):
    """Environment types for configuration management"""
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"


class FeatureToggle(Enum):
    """Feature toggle identifiers"""
    MONITOR_MODE = "monitor_mode"
    ENFORCEMENT_MODE = "enforcement_mode"
    SCHEMA_VALIDATION = "schema_validation"
    WORKFLOW_VALIDATION = "workflow_validation"
    SECURITY_VALIDATION = "security_validation"
    RUNTIME_MONITORING = "runtime_monitoring"
    BACKUP_SYSTEM = "backup_system"
    ALERT_SYSTEM = "alert_system"


@dataclass
class ValidationThresholds:
    """Validation threshold configuration"""
    max_compilation_errors: int = 0
    max_xml_errors: int = 0
    max_schema_inconsistencies: int = 0
    max_security_gaps: int = 0
    max_workflow_errors: int = 0
    false_positive_rate_limit: float = 0.02  # 2%
    validation_timeout_seconds: int = 300  # 5 minutes


@dataclass
class MonitoringThresholds:
    """Runtime monitoring threshold configuration"""
    approval_failure_rate: float = 0.05  # 5%
    rpc_error_rate: float = 0.02  # 2%
    access_violation_count: int = 10  # per hour
    state_transition_errors: int = 5  # per hour
    performance_degradation_threshold: float = 0.05  # 5%


@dataclass
class BackupSettings:
    """Backup and recovery configuration"""
    backup_retention_days: int = 30
    backup_compression: bool = True
    backup_verification: bool = True
    auto_backup_enabled: bool = False  # Disabled in Stage 1
    rollback_enabled: bool = False  # Disabled in Stage 1


@dataclass
class AlertSettings:
    """Alert system configuration"""
    email_enabled: bool = False  # Disabled in Stage 1
    sms_enabled: bool = False  # Disabled in Stage 1
    dashboard_enabled: bool = False  # Disabled in Stage 1
    log_enabled: bool = True  # Only logging enabled in Stage 1
    alert_throttle_minutes: int = 15
    max_alerts_per_hour: int = 20


@dataclass
class SafeguardsConfig:
    """Main safeguards configuration container"""
    environment: Environment = Environment.DEVELOPMENT
    feature_toggles: Dict[FeatureToggle, bool] = field(default_factory=dict)
    validation_thresholds: ValidationThresholds = field(default_factory=ValidationThresholds)
    monitoring_thresholds: MonitoringThresholds = field(default_factory=MonitoringThresholds)
    backup_settings: BackupSettings = field(default_factory=BackupSettings)
    alert_settings: AlertSettings = field(default_factory=AlertSettings)
    
    def __post_init__(self):
        """Initialize default feature toggles for Stage 1"""
        if not self.feature_toggles:
            self.feature_toggles = {
                FeatureToggle.MONITOR_MODE: True,  # Always enabled in Stage 1
                FeatureToggle.ENFORCEMENT_MODE: False,  # Always disabled in Stage 1
                FeatureToggle.SCHEMA_VALIDATION: False,  # Stage 2
                FeatureToggle.WORKFLOW_VALIDATION: False,  # Stage 2
                FeatureToggle.SECURITY_VALIDATION: False,  # Stage 2
                FeatureToggle.RUNTIME_MONITORING: False,  # Stage 2
                FeatureToggle.BACKUP_SYSTEM: False,  # Stage 4
                FeatureToggle.ALERT_SYSTEM: True,  # Stage 1 (log-only)
            }


class DeploymentConfigManager:
    """
    Central configuration manager for production safeguards system.
    
    Provides environment-specific configuration loading, validation,
    and runtime configuration updates without service restart.
    
    SAFETY: All operations are read-only and non-intrusive.
    """
    
    _instance: Optional['DeploymentConfigManager'] = None
    _config: Optional[SafeguardsConfig] = None
    
    def __new__(cls) -> 'DeploymentConfigManager':
        """Singleton pattern to ensure single configuration instance"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        """Initialize configuration manager"""
        if self._config is None:
            try:
                self._config = self._load_configuration()
                _logger.info("Safeguards configuration loaded successfully")
            except Exception as e:
                _logger.error(f"Failed to load safeguards configuration: {e}")
                # Graceful fallback to default configuration
                self._config = SafeguardsConfig()
    
    def _detect_environment(self) -> Environment:
        """
        Detect current environment from various sources.
        
        Returns:
            Environment: Detected environment type
        """
        try:
            # Check environment variable first
            env_var = os.environ.get('ODOO_ENVIRONMENT', '').lower()
            if env_var in ['production', 'prod']:
                return Environment.PRODUCTION
            elif env_var in ['staging', 'stage']:
                return Environment.STAGING
            elif env_var in ['development', 'dev', 'test']:
                return Environment.DEVELOPMENT
            
            # Check database name patterns
            db_name = os.environ.get('PGDATABASE', '').lower()
            if 'prod' in db_name or 'production' in db_name:
                return Environment.PRODUCTION
            elif 'stage' in db_name or 'staging' in db_name:
                return Environment.STAGING
            
            # Default to development for safety
            return Environment.DEVELOPMENT
            
        except Exception as e:
            _logger.warning(f"Environment detection failed: {e}, defaulting to development")
            return Environment.DEVELOPMENT
    
    def _load_configuration(self) -> SafeguardsConfig:
        """
        Load configuration from environment variables and defaults.
        
        Returns:
            SafeguardsConfig: Loaded configuration
        """
        try:
            environment = self._detect_environment()
            
            # Create base configuration
            config = SafeguardsConfig(environment=environment)
            
            # Override with environment-specific settings
            if environment == Environment.PRODUCTION:
                # Production settings - more conservative
                config.validation_thresholds.false_positive_rate_limit = 0.01  # 1%
                config.monitoring_thresholds.approval_failure_rate = 0.02  # 2%
                config.backup_settings.backup_retention_days = 90
            elif environment == Environment.STAGING:
                # Staging settings - moderate
                config.validation_thresholds.false_positive_rate_limit = 0.02  # 2%
                config.monitoring_thresholds.approval_failure_rate = 0.05  # 5%
                config.backup_settings.backup_retention_days = 30
            else:
                # Development settings - permissive
                config.validation_thresholds.false_positive_rate_limit = 0.05  # 5%
                config.monitoring_thresholds.approval_failure_rate = 0.10  # 10%
                config.backup_settings.backup_retention_days = 7
            
            # Apply environment variable overrides
            self._apply_env_overrides(config)
            
            return config
            
        except Exception as e:
            _logger.error(f"Configuration loading failed: {e}")
            # Return safe default configuration
            return SafeguardsConfig()
    
    def _apply_env_overrides(self, config: SafeguardsConfig) -> None:
        """
        Apply environment variable overrides to configuration.
        
        Args:
            config: Configuration to modify
        """
        try:
            # Feature toggle overrides
            if os.environ.get('SAFEGUARDS_MONITOR_MODE', '').lower() == 'false':
                config.feature_toggles[FeatureToggle.MONITOR_MODE] = False
            
            # Emergency disable override
            if os.environ.get('EMERGENCY_BYPASS_ALL_SAFEGUARDS', '').lower() == 'true':
                _logger.warning("EMERGENCY BYPASS: All safeguards disabled via environment variable")
                for toggle in config.feature_toggles:
                    config.feature_toggles[toggle] = False
            
            # Threshold overrides
            false_positive_limit = os.environ.get('SAFEGUARDS_FALSE_POSITIVE_LIMIT')
            if false_positive_limit:
                try:
                    config.validation_thresholds.false_positive_rate_limit = float(false_positive_limit)
                except ValueError:
                    _logger.warning(f"Invalid false positive limit: {false_positive_limit}")
            
        except Exception as e:
            _logger.error(f"Environment override application failed: {e}")
            # Continue with existing configuration
    
    def get_config(self) -> SafeguardsConfig:
        """
        Get current safeguards configuration.
        
        Returns:
            SafeguardsConfig: Current configuration
        """
        if self._config is None:
            self._config = self._load_configuration()
        return self._config
    
    def is_feature_enabled(self, feature: FeatureToggle) -> bool:
        """
        Check if a feature is enabled.
        
        Args:
            feature: Feature to check
            
        Returns:
            bool: True if feature is enabled
        """
        try:
            config = self.get_config()
            return config.feature_toggles.get(feature, False)
        except Exception as e:
            _logger.error(f"Feature check failed for {feature}: {e}")
            return False
    
    def is_monitor_mode(self) -> bool:
        """
        Check if system is in monitor-only mode.
        
        Returns:
            bool: True if in monitor mode
        """
        return self.is_feature_enabled(FeatureToggle.MONITOR_MODE)
    
    def is_enforcement_mode(self) -> bool:
        """
        Check if system is in enforcement mode.
        
        Returns:
            bool: True if in enforcement mode
        """
        # Stage 1: Always return False
        return False
    
    def get_environment(self) -> Environment:
        """
        Get current environment.
        
        Returns:
            Environment: Current environment
        """
        try:
            return self.get_config().environment
        except Exception as e:
            _logger.error(f"Environment retrieval failed: {e}")
            return Environment.DEVELOPMENT
    
    def get_validation_thresholds(self) -> ValidationThresholds:
        """
        Get validation thresholds.
        
        Returns:
            ValidationThresholds: Current validation thresholds
        """
        try:
            return self.get_config().validation_thresholds
        except Exception as e:
            _logger.error(f"Validation thresholds retrieval failed: {e}")
            return ValidationThresholds()
    
    def get_monitoring_thresholds(self) -> MonitoringThresholds:
        """
        Get monitoring thresholds.
        
        Returns:
            MonitoringThresholds: Current monitoring thresholds
        """
        try:
            return self.get_config().monitoring_thresholds
        except Exception as e:
            _logger.error(f"Monitoring thresholds retrieval failed: {e}")
            return MonitoringThresholds()
    
    def reload_configuration(self) -> bool:
        """
        Reload configuration from environment.
        
        Returns:
            bool: True if reload successful
        """
        try:
            old_config = self._config
            self._config = self._load_configuration()
            _logger.info("Configuration reloaded successfully")
            return True
        except Exception as e:
            _logger.error(f"Configuration reload failed: {e}")
            # Restore old configuration
            self._config = old_config
            return False
    
    def validate_configuration(self) -> Dict[str, Any]:
        """
        Validate current configuration and return validation report.
        
        Returns:
            Dict[str, Any]: Validation report
        """
        try:
            config = self.get_config()
            report = {
                'valid': True,
                'errors': [],
                'warnings': [],
                'environment': config.environment.value,
                'monitor_mode': self.is_monitor_mode(),
                'enforcement_mode': self.is_enforcement_mode(),
            }
            
            # Validate thresholds
            if config.validation_thresholds.false_positive_rate_limit > 0.1:
                report['warnings'].append("False positive rate limit is high (>10%)")
            
            if config.monitoring_thresholds.approval_failure_rate > 0.2:
                report['warnings'].append("Approval failure rate threshold is high (>20%)")
            
            # Stage 1 specific validations
            if config.feature_toggles.get(FeatureToggle.ENFORCEMENT_MODE, False):
                report['errors'].append("Enforcement mode must be disabled in Stage 1")
                report['valid'] = False
            
            if not config.feature_toggles.get(FeatureToggle.MONITOR_MODE, True):
                report['warnings'].append("Monitor mode should be enabled in Stage 1")
            
            return report
            
        except Exception as e:
            _logger.error(f"Configuration validation failed: {e}")
            return {
                'valid': False,
                'errors': [f"Validation failed: {e}"],
                'warnings': [],
                'environment': 'unknown',
                'monitor_mode': False,
                'enforcement_mode': False,
            }


# Global configuration manager instance
config_manager = DeploymentConfigManager()


def get_config() -> SafeguardsConfig:
    """
    Get global safeguards configuration.
    
    Returns:
        SafeguardsConfig: Current configuration
    """
    return config_manager.get_config()


def is_feature_enabled(feature: FeatureToggle) -> bool:
    """
    Check if a feature is enabled globally.
    
    Args:
        feature: Feature to check
        
    Returns:
        bool: True if feature is enabled
    """
    return config_manager.is_feature_enabled(feature)


def is_monitor_mode() -> bool:
    """
    Check if system is in monitor-only mode globally.
    
    Returns:
        bool: True if in monitor mode
    """
    return config_manager.is_monitor_mode()


def get_environment() -> Environment:
    """
    Get current environment globally.
    
    Returns:
        Environment: Current environment
    """
    return config_manager.get_environment()