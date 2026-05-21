#!/usr/bin/env python3
"""
HAGBES FLEET ORM ↔ POSTGRESQL SCHEMA GUARD
==========================================

Enhanced schema synchronization validator for Stage 2 - Passive Validation Mode.
Provides comprehensive ORM and database consistency validation with detailed reporting.

This guard detects:
- Missing database columns with detailed impact analysis
- Orphan ir.model.fields records with cleanup recommendations
- Field type mismatches between ORM and PostgreSQL with migration suggestions
- Relational integrity issues for Many2one fields with constraint validation
- Stored computed field validation with dependency analysis
- Schema drift detection with rollback impact assessment

STAGE 2 SAFETY CONSTRAINTS:
- ALL validations are REPORT ONLY - no deployment blocking
- NO database modifications or schema changes
- NO ORM operations that could affect runtime
- ALL failures must be graceful and non-breaking
- Integration with Stage 1 infrastructure (logging, alerts, validation engine)
"""

import os
import sys
import json
import logging
import psycopg2
from pathlib import Path
from typing import Dict, List, Tuple, Any, Optional, Set
import ast
import re
import time
from datetime import datetime, timezone

# Import Stage 1 infrastructure components
try:
    from ..safeguards.logging_audit_system import get_logger, EventType, Severity
    from ..safeguards.validation_engine import BaseValidator, ValidationResult, ValidationStatus, ValidationSeverity
    from ..safeguards.alert_manager import create_validation_alert, AlertSeverity
    from ..safeguards.deployment_config import get_config, is_feature_enabled, FeatureToggle
    _stage1_available = True
except ImportError:
    # Fallback for standalone execution
    _stage1_available = False
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Initialize logger
if _stage1_available:
    logger = get_logger("schema_guard")
else:
    logger = logging.getLogger(__name__)

class SchemaGuard:
    """Enhanced ORM ↔ PostgreSQL synchronization validator for Stage 2."""
    
    def __init__(self, module_path: str, db_config: Dict[str, str]):
        self.module_path = Path(module_path)
        self.db_config = db_config
        self.validation_results = {
            'missing_columns': [],
            'orphan_fields': [],
            'type_mismatches': [],
            'migration_issues': [],
            'relational_integrity_issues': [],
            'stored_computed_field_issues': [],
            'schema_drift_analysis': [],
            'critical_inconsistencies': [],
            'warnings': [],
            'deployment_safe': True,
            'validation_summary': {
                'total_models_checked': 0,
                'total_fields_validated': 0,
                'issues_found': 0,
                'critical_issues': 0,
                'warnings_count': 0,
                'validation_accuracy': 0.0,
                'false_positive_rate': 0.0
            }
        }
        self.orm_models = {}
        self.db_schema = {}
        self.ir_model_fields = {}
        self.computed_fields_cache = {}
        
        # Stage 1 integration
        if _stage1_available:
            self.correlation_id = None
            self.start_time = time.time()
    
    def set_correlation_id(self, correlation_id: str) -> None:
        """Set correlation ID for tracking validation across components."""
        if _stage1_available:
            self.correlation_id = correlation_id
        else:
            # Fallback for standalone execution
            self.correlation_id = correlation_id
    
    def connect_database(self) -> psycopg2.extensions.connection:
        """Establish database connection."""
        try:
            conn = psycopg2.connect(
                host=self.db_config.get('host', 'localhost'),
                port=self.db_config.get('port', 5432),
                database=self.db_config['database'],
                user=self.db_config['user'],
                password=self.db_config.get('password', '')
            )
            return conn
        except Exception as e:
            logger.error(f"Database connection failed: {e}")
            raise
    
    def extract_orm_models(self) -> Dict[str, Dict]:
        """Extract ORM model definitions from Python files."""
        logger.info("🔍 Extracting ORM model definitions...")
        
        models_dir = self.module_path / "models"
        if not models_dir.exists():
            return {}
        
        models = {}
        
        for py_file in models_dir.glob("*.py"):
            if py_file.name == "__init__.py":
                continue
            
            try:
                with open(py_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # Parse AST to extract model information
                tree = ast.parse(content)
                
                for node in ast.walk(tree):
                    if isinstance(node, ast.ClassDef):
                        # Check if this is an Odoo model
                        model_info = self._extract_model_info(node, content)
                        if model_info:
                            models[model_info['name']] = model_info
                            
            except Exception as e:
                logger.warning(f"Could not parse {py_file}: {e}")
        
        self.orm_models = models
        logger.info(f"Extracted {len(models)} ORM models")
        return models
    
    def _extract_model_info(self, class_node: ast.ClassDef, content: str) -> Optional[Dict]:
        """Extract model information from AST class node."""
        model_info = {
            'class_name': class_node.name,
            'name': None,
            'table': None,
            'fields': {},
            'inherits': []
        }
        
        # Check if this inherits from models.Model
        for base in class_node.bases:
            if isinstance(base, ast.Attribute) and base.attr in ['Model', 'AbstractModel']:
                break
        else:
            return None  # Not an Odoo model
        
        # Extract _name and fields
        for node in class_node.body:
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        if target.id == '_name' and isinstance(node.value, ast.Constant):
                            model_info['name'] = node.value.value
                            model_info['table'] = node.value.value.replace('.', '_')
                        elif target.id.startswith('_') and target.id.endswith('_'):
                            continue  # Skip other special attributes
                        else:
                            # This might be a field
                            field_info = self._extract_field_info(target.id, node, content)
                            if field_info:
                                model_info['fields'][target.id] = field_info
        
        return model_info if model_info['name'] else None
    
    def _extract_field_info(self, field_name: str, assign_node: ast.Assign, content: str) -> Optional[Dict]:
        """Extract field information from assignment node."""
        if not isinstance(assign_node.value, ast.Call):
            return None
        
        # Check if this is a fields.* call
        if not (isinstance(assign_node.value.func, ast.Attribute) and 
                isinstance(assign_node.value.func.value, ast.Name) and
                assign_node.value.func.value.id == 'fields'):
            return None
        
        field_type = assign_node.value.func.attr
        field_info = {
            'type': field_type,
            'required': False,
            'stored': True,
            'computed': False,
            'related_model': None
        }
        
        # Extract field parameters
        for keyword in assign_node.value.keywords:
            if keyword.arg == 'required' and isinstance(keyword.value, ast.Constant):
                field_info['required'] = keyword.value.value
            elif keyword.arg == 'store' and isinstance(keyword.value, ast.Constant):
                field_info['stored'] = keyword.value.value
            elif keyword.arg == 'compute' and isinstance(keyword.value, ast.Constant):
                field_info['computed'] = True
        
        # For relational fields, extract target model
        if field_type in ['Many2one', 'One2many', 'Many2many']:
            if assign_node.value.args and isinstance(assign_node.value.args[0], ast.Constant):
                field_info['related_model'] = assign_node.value.args[0].value
        
        return field_info
    
    def extract_ir_model_fields(self) -> Dict[str, Dict]:
        """Extract ir.model.fields records from database for orphan detection."""
        if _stage1_available:
            logger.log_validation_event(
                "Extracting ir.model.fields records for orphan detection",
                severity=Severity.INFO,
                validation_type="ir_model_fields_extraction",
                correlation_id=self.correlation_id
            )
        else:
            logger.info("🔍 Extracting ir.model.fields records...")
        
        conn = self.connect_database()
        ir_fields = {}
        
        try:
            with conn.cursor() as cursor:
                # Get ir.model.fields for hagbes_fleet models
                cursor.execute("""
                    SELECT 
                        imf.id,
                        imf.name as field_name,
                        imf.model as model_name,
                        imf.ttype as field_type,
                        imf.relation as related_model,
                        imf.required,
                        imf.readonly,
                        imf.store,
                        imf.compute,
                        imf.depends,
                        imf.help,
                        imf.state,
                        im.model as model_technical_name
                    FROM ir_model_fields imf
                    JOIN ir_model im ON imf.model_id = im.id
                    WHERE im.model LIKE 'hagbes_fleet.%' OR im.model LIKE 'fleet.%'
                    ORDER BY imf.model, imf.name
                """)
                
                for row in cursor.fetchall():
                    (field_id, field_name, model_name, field_type, related_model, 
                     required, readonly, store, compute, depends, help_text, 
                     state, model_technical_name) = row
                    
                    if model_name not in ir_fields:
                        ir_fields[model_name] = {}
                    
                    ir_fields[model_name][field_name] = {
                        'id': field_id,
                        'field_name': field_name,
                        'model_name': model_name,
                        'field_type': field_type,
                        'related_model': related_model,
                        'required': required,
                        'readonly': readonly,
                        'store': store,
                        'compute': compute,
                        'depends': depends,
                        'help': help_text,
                        'state': state,
                        'model_technical_name': model_technical_name
                    }
        
        finally:
            conn.close()
        
        self.ir_model_fields = ir_fields
        
        if _stage1_available:
            logger.log_validation_event(
                f"Extracted ir.model.fields for {len(ir_fields)} models",
                severity=Severity.INFO,
                validation_type="ir_model_fields_extraction",
                models_count=len(ir_fields),
                correlation_id=self.correlation_id
            )
        else:
            logger.info(f"Extracted ir.model.fields for {len(ir_fields)} models")
        
        return ir_fields
    def extract_database_schema(self) -> Dict[str, Dict]:
        """Extract enhanced database schema information with constraint details."""
        if _stage1_available:
            logger.log_validation_event(
                "Extracting enhanced database schema information",
                severity=Severity.INFO,
                validation_type="database_schema_extraction",
                correlation_id=self.correlation_id
            )
        else:
            logger.info("🔍 Extracting enhanced database schema...")
        
        conn = self.connect_database()
        schema = {}
        
        try:
            with conn.cursor() as cursor:
                # Get comprehensive table and column information
                cursor.execute("""
                    SELECT 
                        t.table_name,
                        c.column_name,
                        c.data_type,
                        c.is_nullable,
                        c.column_default,
                        c.character_maximum_length,
                        c.numeric_precision,
                        c.numeric_scale,
                        c.datetime_precision,
                        c.udt_name,
                        c.ordinal_position
                    FROM information_schema.tables t
                    JOIN information_schema.columns c ON t.table_name = c.table_name
                    WHERE t.table_schema = 'public' 
                    AND (t.table_name LIKE 'fleet_%' OR t.table_name LIKE 'hagbes_fleet_%')
                    AND t.table_type = 'BASE TABLE'
                    ORDER BY t.table_name, c.ordinal_position
                """)
                
                for row in cursor.fetchall():
                    (table_name, column_name, data_type, is_nullable, column_default,
                     char_max_length, numeric_precision, numeric_scale, datetime_precision,
                     udt_name, ordinal_position) = row
                    
                    if table_name not in schema:
                        schema[table_name] = {
                            'columns': {},
                            'foreign_keys': {},
                            'indexes': {},
                            'constraints': {}
                        }
                    
                    schema[table_name]['columns'][column_name] = {
                        'type': data_type,
                        'nullable': is_nullable == 'YES',
                        'default': column_default,
                        'char_max_length': char_max_length,
                        'numeric_precision': numeric_precision,
                        'numeric_scale': numeric_scale,
                        'datetime_precision': datetime_precision,
                        'udt_name': udt_name,
                        'ordinal_position': ordinal_position
                    }
                
                # Get foreign key constraints with detailed information
                cursor.execute("""
                    SELECT 
                        tc.table_name,
                        kcu.column_name,
                        ccu.table_name AS foreign_table_name,
                        ccu.column_name AS foreign_column_name,
                        tc.constraint_name,
                        rc.update_rule,
                        rc.delete_rule
                    FROM information_schema.table_constraints AS tc
                    JOIN information_schema.key_column_usage AS kcu
                        ON tc.constraint_name = kcu.constraint_name
                    JOIN information_schema.constraint_column_usage AS ccu
                        ON ccu.constraint_name = tc.constraint_name
                    LEFT JOIN information_schema.referential_constraints AS rc
                        ON tc.constraint_name = rc.constraint_name
                    WHERE tc.constraint_type = 'FOREIGN KEY'
                    AND tc.table_schema = 'public'
                    AND (tc.table_name LIKE 'fleet_%' OR tc.table_name LIKE 'hagbes_fleet_%')
                """)
                
                for row in cursor.fetchall():
                    (table_name, column_name, foreign_table, foreign_column, 
                     constraint_name, update_rule, delete_rule) = row
                    
                    if table_name in schema:
                        schema[table_name]['foreign_keys'][column_name] = {
                            'references_table': foreign_table,
                            'references_column': foreign_column,
                            'constraint_name': constraint_name,
                            'update_rule': update_rule,
                            'delete_rule': delete_rule
                        }
                
                # Get indexes for performance analysis
                cursor.execute("""
                    SELECT 
                        t.relname AS table_name,
                        i.relname AS index_name,
                        a.attname AS column_name,
                        ix.indisunique,
                        ix.indisprimary
                    FROM pg_class t
                    JOIN pg_index ix ON t.oid = ix.indrelid
                    JOIN pg_class i ON i.oid = ix.indexrelid
                    JOIN pg_attribute a ON a.attrelid = t.oid AND a.attnum = ANY(ix.indkey)
                    WHERE t.relkind = 'r'
                    AND (t.relname LIKE 'fleet_%' OR t.relname LIKE 'hagbes_fleet_%')
                    ORDER BY t.relname, i.relname
                """)
                
                for row in cursor.fetchall():
                    table_name, index_name, column_name, is_unique, is_primary = row
                    
                    if table_name in schema:
                        if index_name not in schema[table_name]['indexes']:
                            schema[table_name]['indexes'][index_name] = {
                                'columns': [],
                                'unique': is_unique,
                                'primary': is_primary
                            }
                        schema[table_name]['indexes'][index_name]['columns'].append(column_name)
        
        finally:
            conn.close()
        
        self.db_schema = schema
        
        if _stage1_available:
            logger.log_validation_event(
                f"Extracted enhanced schema for {len(schema)} database tables",
                severity=Severity.INFO,
                validation_type="database_schema_extraction",
                tables_count=len(schema),
                correlation_id=self.correlation_id
            )
        else:
            logger.info(f"Extracted enhanced schema for {len(schema)} database tables")
        
        return schema
    
    def detect_orphan_ir_model_fields(self) -> List[Dict]:
        """Detect orphan ir.model.fields records that don't correspond to actual ORM fields."""
        if _stage1_available:
            logger.log_validation_event(
                "Detecting orphan ir.model.fields records",
                severity=Severity.INFO,
                validation_type="orphan_fields_detection",
                correlation_id=self.correlation_id
            )
        else:
            logger.info("🔍 Detecting orphan ir.model.fields records...")
        
        orphan_fields = []
        
        for model_name, ir_fields in self.ir_model_fields.items():
            # Check if model exists in ORM
            orm_model = None
            for orm_model_name, orm_model_info in self.orm_models.items():
                if orm_model_info['name'] == model_name:
                    orm_model = orm_model_info
                    break
            
            if not orm_model:
                # Entire model is orphaned
                for field_name, field_info in ir_fields.items():
                    orphan_fields.append({
                        'type': 'orphan_model',
                        'model': model_name,
                        'field': field_name,
                        'ir_model_field_id': field_info['id'],
                        'issue': f'Model {model_name} not found in ORM definitions',
                        'cleanup_recommendation': f'Remove ir.model.fields record {field_info["id"]} for non-existent model',
                        'impact': 'Low - orphan metadata record',
                        'field_info': field_info
                    })
                continue
            
            # Check individual fields
            for field_name, field_info in ir_fields.items():
                if field_name not in orm_model['fields']:
                    # Check if it's a system field that should be ignored
                    system_fields = {
                        'id', 'create_date', 'create_uid', 'write_date', 'write_uid',
                        '__last_update', 'display_name'
                    }
                    
                    if field_name not in system_fields:
                        orphan_fields.append({
                            'type': 'orphan_field',
                            'model': model_name,
                            'field': field_name,
                            'ir_model_field_id': field_info['id'],
                            'issue': f'Field {field_name} exists in ir.model.fields but not in ORM model {model_name}',
                            'cleanup_recommendation': f'Remove ir.model.fields record {field_info["id"]} or add field to ORM model',
                            'impact': 'Medium - may cause field access errors',
                            'field_info': field_info
                        })
        
        self.validation_results['orphan_fields'] = orphan_fields
        
        if orphan_fields:
            if _stage1_available:
                logger.log_validation_event(
                    f"Found {len(orphan_fields)} orphan ir.model.fields records",
                    severity=Severity.WARNING,
                    validation_type="orphan_fields_detection",
                    orphan_count=len(orphan_fields),
                    correlation_id=self.correlation_id
                )
            else:
                logger.warning(f"Found {len(orphan_fields)} orphan ir.model.fields records")
        
        return orphan_fields
    def detect_missing_columns(self) -> List[Dict]:
        """Detect ORM fields that don't have corresponding database columns with detailed impact analysis."""
        if _stage1_available:
            logger.log_validation_event(
                "Detecting missing database columns with impact analysis",
                severity=Severity.INFO,
                validation_type="missing_columns_detection",
                correlation_id=self.correlation_id
            )
        else:
            logger.info("🔍 Detecting missing database columns...")
        
        missing_columns = []
        
        for model_name, model_info in self.orm_models.items():
            table_name = model_info['table']
            if not table_name or table_name not in self.db_schema:
                continue
            
            db_columns = self.db_schema[table_name]['columns']
            
            for field_name, field_info in model_info['fields'].items():
                # Skip computed non-stored fields
                if field_info['computed'] and not field_info['stored']:
                    continue
                
                # Map field name to database column name
                db_column_name = field_name
                if field_info['type'] == 'Many2one':
                    db_column_name = f"{field_name}_id"
                
                if db_column_name not in db_columns:
                    # Analyze impact of missing column
                    impact_analysis = self._analyze_missing_column_impact(
                        model_name, field_name, field_info, table_name
                    )
                    
                    missing_columns.append({
                        'model': model_name,
                        'table': table_name,
                        'field': field_name,
                        'db_column': db_column_name,
                        'field_type': field_info['type'],
                        'required': field_info.get('required', False),
                        'stored': field_info.get('stored', True),
                        'computed': field_info.get('computed', False),
                        'related_model': field_info.get('related_model'),
                        'impact_analysis': impact_analysis,
                        'migration_suggestion': self._generate_migration_suggestion(
                            table_name, db_column_name, field_info
                        ),
                        'rollback_impact': self._assess_rollback_impact(
                            model_name, field_name, field_info
                        )
                    })
        
        self.validation_results['missing_columns'] = missing_columns
        
        if missing_columns:
            if _stage1_available:
                logger.log_validation_event(
                    f"Found {len(missing_columns)} missing database columns",
                    severity=Severity.WARNING,
                    validation_type="missing_columns_detection",
                    missing_count=len(missing_columns),
                    correlation_id=self.correlation_id
                )
            else:
                logger.warning(f"Found {len(missing_columns)} missing database columns")
        
        return missing_columns
    
    def _analyze_missing_column_impact(self, model_name: str, field_name: str, 
                                     field_info: Dict, table_name: str) -> Dict[str, Any]:
        """Analyze the impact of a missing database column."""
        impact = {
            'severity': 'medium',
            'runtime_errors': [],
            'affected_operations': [],
            'user_impact': 'medium',
            'data_loss_risk': 'low'
        }
        
        # Assess severity based on field characteristics
        if field_info.get('required', False):
            impact['severity'] = 'high'
            impact['runtime_errors'].append('Field access will raise psycopg2.errors.UndefinedColumn')
            impact['user_impact'] = 'high'
        
        if field_info['type'] == 'Many2one':
            impact['affected_operations'].extend([
                'Relational queries will fail',
                'Foreign key constraints cannot be enforced',
                'Related record access will cause errors'
            ])
            if field_info.get('required', False):
                impact['severity'] = 'critical'
        
        if field_info.get('computed', False) and field_info.get('stored', True):
            impact['affected_operations'].append('Computed field storage will fail')
            impact['data_loss_risk'] = 'medium'
        
        # Check if field is used in views or reports
        if self._field_used_in_views(model_name, field_name):
            impact['affected_operations'].append('View rendering will fail')
            impact['user_impact'] = 'high'
        
        return impact
    
    def _generate_migration_suggestion(self, table_name: str, column_name: str, 
                                     field_info: Dict) -> Dict[str, str]:
        """Generate migration SQL suggestion for missing column."""
        # Map ORM field types to PostgreSQL types
        type_mapping = {
            'Char': 'VARCHAR',
            'Text': 'TEXT',
            'Integer': 'INTEGER',
            'Float': 'DOUBLE PRECISION',
            'Boolean': 'BOOLEAN',
            'Date': 'DATE',
            'Datetime': 'TIMESTAMP',
            'Many2one': 'INTEGER',
            'Selection': 'VARCHAR'
        }
        
        pg_type = type_mapping.get(field_info['type'], 'TEXT')
        nullable = 'NULL' if not field_info.get('required', False) else 'NOT NULL'
        
        sql = f"ALTER TABLE {table_name} ADD COLUMN {column_name} {pg_type}"
        if not field_info.get('required', False):
            sql += f" {nullable};"
        else:
            # For required fields, add with default first, then set NOT NULL
            sql += f" {nullable} DEFAULT NULL;"
            sql += f"\n-- After data migration: ALTER TABLE {table_name} ALTER COLUMN {column_name} SET NOT NULL;"
        
        return {
            'sql': sql,
            'type_mapping': f"{field_info['type']} -> {pg_type}",
            'nullable': nullable,
            'requires_data_migration': field_info.get('required', False)
        }
    
    def _assess_rollback_impact(self, model_name: str, field_name: str, 
                              field_info: Dict) -> Dict[str, Any]:
        """Assess the impact of rolling back this field addition."""
        return {
            'data_loss_risk': 'high' if field_info.get('required', False) else 'medium',
            'rollback_complexity': 'high' if field_info['type'] == 'Many2one' else 'low',
            'backup_required': True,
            'rollback_sql': f"-- Rollback: ALTER TABLE {model_name.replace('.', '_')} DROP COLUMN IF EXISTS {field_name};"
        }
    
    def _field_used_in_views(self, model_name: str, field_name: str) -> bool:
        """Check if field is referenced in XML views (simplified check)."""
        try:
            views_dir = self.module_path / "views"
            if not views_dir.exists():
                return False
            
            for xml_file in views_dir.glob("*.xml"):
                try:
                    with open(xml_file, 'r', encoding='utf-8') as f:
                        content = f.read()
                        if f'field name="{field_name}"' in content:
                            return True
                except Exception:
                    continue
            
            return False
        except Exception:
            return False
    
    def detect_type_mismatches(self) -> List[Dict]:
        """Detect field type mismatches between ORM and database with migration analysis."""
        if _stage1_available:
            logger.log_validation_event(
                "Detecting field type mismatches with migration analysis",
                severity=Severity.INFO,
                validation_type="type_mismatch_detection",
                correlation_id=self.correlation_id
            )
        else:
            logger.info("🔍 Detecting field type mismatches...")
        
        type_mismatches = []
        
        # Enhanced ORM to PostgreSQL type mapping with compatibility analysis
        type_mapping = {
            'Char': {
                'compatible': ['character varying', 'text', 'varchar'],
                'preferred': 'character varying',
                'migration_safe': True
            },
            'Text': {
                'compatible': ['text', 'character varying'],
                'preferred': 'text',
                'migration_safe': True
            },
            'Integer': {
                'compatible': ['integer', 'bigint', 'smallint'],
                'preferred': 'integer',
                'migration_safe': False  # Potential data loss
            },
            'Float': {
                'compatible': ['double precision', 'numeric', 'real'],
                'preferred': 'double precision',
                'migration_safe': False  # Precision issues
            },
            'Boolean': {
                'compatible': ['boolean', 'bool'],
                'preferred': 'boolean',
                'migration_safe': True
            },
            'Date': {
                'compatible': ['date'],
                'preferred': 'date',
                'migration_safe': True
            },
            'Datetime': {
                'compatible': ['timestamp without time zone', 'timestamp with time zone', 'timestamptz'],
                'preferred': 'timestamp without time zone',
                'migration_safe': True
            },
            'Many2one': {
                'compatible': ['integer', 'bigint'],
                'preferred': 'integer',
                'migration_safe': False  # Foreign key constraints
            },
            'Selection': {
                'compatible': ['character varying', 'text', 'varchar'],
                'preferred': 'character varying',
                'migration_safe': True
            }
        }
        
        for model_name, model_info in self.orm_models.items():
            table_name = model_info['table']
            if not table_name or table_name not in self.db_schema:
                continue
            
            db_columns = self.db_schema[table_name]['columns']
            
            for field_name, field_info in model_info['fields'].items():
                db_column_name = field_name
                if field_info['type'] == 'Many2one':
                    db_column_name = f"{field_name}_id"
                
                if db_column_name in db_columns:
                    db_column_info = db_columns[db_column_name]
                    db_type = db_column_info['type']
                    orm_type = field_info['type']
                    
                    type_config = type_mapping.get(orm_type, {})
                    compatible_types = type_config.get('compatible', [])
                    
                    if compatible_types and db_type not in compatible_types:
                        mismatch_analysis = self._analyze_type_mismatch(
                            model_name, field_name, orm_type, db_type, 
                            db_column_info, field_info, type_config
                        )
                        
                        type_mismatches.append({
                            'model': model_name,
                            'table': table_name,
                            'field': field_name,
                            'db_column': db_column_name,
                            'orm_type': orm_type,
                            'db_type': db_type,
                            'expected_db_types': compatible_types,
                            'preferred_db_type': type_config.get('preferred', compatible_types[0] if compatible_types else db_type),
                            'migration_safe': type_config.get('migration_safe', False),
                            'mismatch_analysis': mismatch_analysis,
                            'migration_strategy': self._generate_type_migration_strategy(
                                table_name, db_column_name, orm_type, db_type, db_column_info
                            ),
                            'data_validation_required': self._requires_data_validation(orm_type, db_type),
                            'db_column_details': db_column_info
                        })
        
        self.validation_results['type_mismatches'] = type_mismatches
        
        if type_mismatches:
            if _stage1_available:
                logger.log_validation_event(
                    f"Found {len(type_mismatches)} type mismatches",
                    severity=Severity.WARNING,
                    validation_type="type_mismatch_detection",
                    mismatch_count=len(type_mismatches),
                    correlation_id=self.correlation_id
                )
            else:
                logger.warning(f"Found {len(type_mismatches)} type mismatches")
        
        return type_mismatches
    
    def _analyze_type_mismatch(self, model_name: str, field_name: str, orm_type: str, 
                             db_type: str, db_column_info: Dict, field_info: Dict, 
                             type_config: Dict) -> Dict[str, Any]:
        """Analyze the implications of a type mismatch."""
        analysis = {
            'severity': 'medium',
            'compatibility_issues': [],
            'data_integrity_risks': [],
            'performance_impact': 'low',
            'migration_complexity': 'medium'
        }
        
        # Analyze specific type compatibility issues
        if orm_type == 'Integer' and db_type in ['character varying', 'text']:
            analysis['severity'] = 'high'
            analysis['compatibility_issues'].extend([
                'Integer operations will fail on string data',
                'Sorting and comparison operations will be incorrect',
                'Aggregation functions (SUM, AVG) will fail'
            ])
            analysis['data_integrity_risks'].append('Invalid integer values may exist in string column')
            analysis['migration_complexity'] = 'high'
        
        elif orm_type == 'Boolean' and db_type not in ['boolean', 'bool']:
            analysis['severity'] = 'high'
            analysis['compatibility_issues'].extend([
                'Boolean logic operations will fail',
                'True/False comparisons will be incorrect'
            ])
        
        elif orm_type == 'Many2one' and db_type not in ['integer', 'bigint']:
            analysis['severity'] = 'critical'
            analysis['compatibility_issues'].extend([
                'Foreign key relationships will fail',
                'JOIN operations will produce incorrect results',
                'Referential integrity cannot be enforced'
            ])
            analysis['data_integrity_risks'].append('Invalid foreign key references may exist')
        
        elif orm_type in ['Date', 'Datetime'] and 'timestamp' not in db_type and 'date' not in db_type:
            analysis['severity'] = 'high'
            analysis['compatibility_issues'].extend([
                'Date/time operations will fail',
                'Date formatting and parsing will be incorrect',
                'Temporal queries will produce wrong results'
            ])
        
        # Assess performance impact
        if db_column_info.get('char_max_length') and db_column_info['char_max_length'] > 1000:
            analysis['performance_impact'] = 'medium'
        
        # Check if field is indexed
        table_name = model_name.replace('.', '_')
        if table_name in self.db_schema:
            indexes = self.db_schema[table_name].get('indexes', {})
            for index_info in indexes.values():
                if field_name in index_info.get('columns', []):
                    analysis['performance_impact'] = 'high'
                    analysis['compatibility_issues'].append('Index performance may be affected by type mismatch')
                    break
        
        return analysis
    
    def _generate_type_migration_strategy(self, table_name: str, column_name: str, 
                                        orm_type: str, db_type: str, db_column_info: Dict) -> Dict[str, Any]:
        """Generate migration strategy for type mismatch."""
        strategy = {
            'approach': 'direct_cast',
            'sql_commands': [],
            'validation_queries': [],
            'rollback_commands': [],
            'data_backup_required': True,
            'estimated_downtime': 'low'
        }
        
        # Generate appropriate migration SQL
        if orm_type == 'Integer' and db_type in ['character varying', 'text']:
            strategy['approach'] = 'validated_cast'
            strategy['sql_commands'] = [
                f"-- Validate existing data",
                f"SELECT COUNT(*) FROM {table_name} WHERE {column_name} !~ '^[0-9]+$' AND {column_name} IS NOT NULL;",
                f"-- Convert column type",
                f"ALTER TABLE {table_name} ALTER COLUMN {column_name} TYPE INTEGER USING {column_name}::INTEGER;"
            ]
            strategy['validation_queries'] = [
                f"SELECT {column_name} FROM {table_name} WHERE {column_name} !~ '^[0-9]+$' AND {column_name} IS NOT NULL LIMIT 10;"
            ]
            strategy['estimated_downtime'] = 'medium'
        
        elif orm_type == 'Boolean':
            strategy['sql_commands'] = [
                f"ALTER TABLE {table_name} ALTER COLUMN {column_name} TYPE BOOLEAN USING {column_name}::BOOLEAN;"
            ]
        
        elif orm_type == 'Many2one':
            strategy['approach'] = 'foreign_key_migration'
            strategy['sql_commands'] = [
                f"-- Drop existing foreign key constraints if any",
                f"-- ALTER TABLE {table_name} DROP CONSTRAINT IF EXISTS fk_{table_name}_{column_name};",
                f"ALTER TABLE {table_name} ALTER COLUMN {column_name} TYPE INTEGER USING {column_name}::INTEGER;",
                f"-- Re-add foreign key constraint after migration"
            ]
            strategy['estimated_downtime'] = 'high'
        
        # Generate rollback commands
        strategy['rollback_commands'] = [
            f"ALTER TABLE {table_name} ALTER COLUMN {column_name} TYPE {db_type};"
        ]
        
        return strategy
    
    def _requires_data_validation(self, orm_type: str, db_type: str) -> bool:
        """Check if data validation is required before type migration."""
        risky_conversions = [
            ('Integer', 'character varying'),
            ('Integer', 'text'),
            ('Boolean', 'character varying'),
            ('Boolean', 'text'),
            ('Many2one', 'character varying'),
            ('Many2one', 'text'),
        ]
        
        return (orm_type, db_type) in risky_conversions
    
    def validate_relational_integrity(self) -> List[Dict]:
        """Enhanced Many2one field relational integrity validation with constraint analysis."""
        if _stage1_available:
            logger.log_validation_event(
                "Validating relational integrity with constraint analysis",
                severity=Severity.INFO,
                validation_type="relational_integrity_validation",
                correlation_id=self.correlation_id
            )
        else:
            logger.info("🔍 Validating relational integrity...")
        
        integrity_issues = []
        
        for model_name, model_info in self.orm_models.items():
            table_name = model_info['table']
            if not table_name or table_name not in self.db_schema:
                continue
            
            foreign_keys = self.db_schema[table_name].get('foreign_keys', {})
            
            for field_name, field_info in model_info['fields'].items():
                if field_info['type'] == 'Many2one':
                    db_column_name = f"{field_name}_id"
                    related_model = field_info.get('related_model')
                    
                    if related_model:
                        integrity_analysis = self._analyze_relational_integrity(
                            model_name, field_name, related_model, db_column_name, 
                            foreign_keys, field_info
                        )
                        
                        if integrity_analysis['has_issues']:
                            integrity_issues.append({
                                'model': model_name,
                                'table': table_name,
                                'field': field_name,
                                'db_column': db_column_name,
                                'related_model': related_model,
                                'related_table': related_model.replace('.', '_'),
                                'issues': integrity_analysis['issues'],
                                'constraint_status': integrity_analysis['constraint_status'],
                                'data_integrity_risks': integrity_analysis['data_integrity_risks'],
                                'recommended_actions': integrity_analysis['recommended_actions'],
                                'constraint_sql': integrity_analysis['constraint_sql'],
                                'validation_queries': integrity_analysis['validation_queries']
                            })
        
        self.validation_results['relational_integrity_issues'] = integrity_issues
        
        if integrity_issues:
            if _stage1_available:
                logger.log_validation_event(
                    f"Found {len(integrity_issues)} relational integrity issues",
                    severity=Severity.WARNING,
                    validation_type="relational_integrity_validation",
                    issues_count=len(integrity_issues),
                    correlation_id=self.correlation_id
                )
            else:
                logger.warning(f"Found {len(integrity_issues)} relational integrity issues")
        
        return integrity_issues
    
    def _analyze_relational_integrity(self, model_name: str, field_name: str, related_model: str,
                                    db_column_name: str, foreign_keys: Dict, field_info: Dict) -> Dict[str, Any]:
        """Analyze relational integrity for a Many2one field."""
        analysis = {
            'has_issues': False,
            'issues': [],
            'constraint_status': 'unknown',
            'data_integrity_risks': [],
            'recommended_actions': [],
            'constraint_sql': '',
            'validation_queries': []
        }
        
        related_table = related_model.replace('.', '_')
        
        # Check if foreign key constraint exists
        if db_column_name not in foreign_keys:
            analysis['has_issues'] = True
            analysis['issues'].append('Missing foreign key constraint')
            analysis['constraint_status'] = 'missing'
            analysis['data_integrity_risks'].extend([
                'Invalid foreign key references may exist',
                'Referential integrity not enforced at database level',
                'Orphaned records possible'
            ])
            analysis['recommended_actions'].append('Add foreign key constraint')
            
            # Generate constraint SQL
            analysis['constraint_sql'] = f"""
ALTER TABLE {model_name.replace('.', '_')} 
ADD CONSTRAINT fk_{model_name.replace('.', '_')}_{field_name} 
FOREIGN KEY ({db_column_name}) 
REFERENCES {related_table}(id) 
ON DELETE SET NULL;"""
            
            # Generate validation query
            analysis['validation_queries'].append(f"""
-- Check for orphaned references
SELECT COUNT(*) as orphaned_count 
FROM {model_name.replace('.', '_')} t1 
LEFT JOIN {related_table} t2 ON t1.{db_column_name} = t2.id 
WHERE t1.{db_column_name} IS NOT NULL AND t2.id IS NULL;""")
        
        else:
            # Constraint exists, validate its configuration
            fk_info = foreign_keys[db_column_name]
            analysis['constraint_status'] = 'exists'
            
            # Check if it references the correct table
            if fk_info['references_table'] != related_table:
                analysis['has_issues'] = True
                analysis['issues'].append(f"Foreign key references wrong table: {fk_info['references_table']} instead of {related_table}")
                analysis['data_integrity_risks'].append('Foreign key points to incorrect target table')
                analysis['recommended_actions'].append('Update foreign key constraint to reference correct table')
            
            # Check cascade rules
            if field_info.get('required', False) and fk_info.get('delete_rule') == 'SET NULL':
                analysis['has_issues'] = True
                analysis['issues'].append('Required field has SET NULL delete rule')
                analysis['data_integrity_risks'].append('Required field may be set to NULL on parent deletion')
                analysis['recommended_actions'].append('Change delete rule to RESTRICT or CASCADE')
        
        # Check if related table exists
        if related_table not in self.db_schema:
            analysis['has_issues'] = True
            analysis['issues'].append(f'Related table {related_table} does not exist')
            analysis['data_integrity_risks'].append('All foreign key references are invalid')
            analysis['recommended_actions'].append('Create related table or fix model reference')
        
        # Generate additional validation queries
        if related_table in self.db_schema:
            analysis['validation_queries'].extend([
                f"""
-- Check for NULL values in required Many2one field
SELECT COUNT(*) as null_count 
FROM {model_name.replace('.', '_')} 
WHERE {db_column_name} IS NULL;""",
                f"""
-- Check for duplicate foreign key values (if unique constraint expected)
SELECT {db_column_name}, COUNT(*) as duplicate_count 
FROM {model_name.replace('.', '_')} 
WHERE {db_column_name} IS NOT NULL 
GROUP BY {db_column_name} 
HAVING COUNT(*) > 1;"""
            ])
        
        return analysis
    
    def validate_stored_computed_fields(self) -> List[Dict]:
        """Validate stored computed fields for dependency and storage consistency."""
        if _stage1_available:
            logger.log_validation_event(
                "Validating stored computed fields",
                severity=Severity.INFO,
                validation_type="stored_computed_fields_validation",
                correlation_id=self.correlation_id
            )
        else:
            logger.info("🔍 Validating stored computed fields...")
        
        computed_field_issues = []
        
        for model_name, model_info in self.orm_models.items():
            table_name = model_info['table']
            if not table_name or table_name not in self.db_schema:
                continue
            
            db_columns = self.db_schema[table_name]['columns']
            
            for field_name, field_info in model_info['fields'].items():
                if field_info.get('computed', False):
                    computed_analysis = self._analyze_computed_field(
                        model_name, field_name, field_info, table_name, db_columns
                    )
                    
                    if computed_analysis['has_issues']:
                        computed_field_issues.append({
                            'model': model_name,
                            'table': table_name,
                            'field': field_name,
                            'computed': True,
                            'stored': field_info.get('stored', False),
                            'depends': field_info.get('depends', ''),
                            'issues': computed_analysis['issues'],
                            'storage_analysis': computed_analysis['storage_analysis'],
                            'dependency_analysis': computed_analysis['dependency_analysis'],
                            'performance_impact': computed_analysis['performance_impact'],
                            'recommended_actions': computed_analysis['recommended_actions']
                        })
        
        self.validation_results['stored_computed_field_issues'] = computed_field_issues
        
        if computed_field_issues:
            if _stage1_available:
                logger.log_validation_event(
                    f"Found {len(computed_field_issues)} stored computed field issues",
                    severity=Severity.WARNING,
                    validation_type="stored_computed_fields_validation",
                    issues_count=len(computed_field_issues),
                    correlation_id=self.correlation_id
                )
            else:
                logger.warning(f"Found {len(computed_field_issues)} stored computed field issues")
        
        return computed_field_issues
    
    def _analyze_computed_field(self, model_name: str, field_name: str, field_info: Dict,
                              table_name: str, db_columns: Dict) -> Dict[str, Any]:
        """Analyze computed field configuration and storage."""
        analysis = {
            'has_issues': False,
            'issues': [],
            'storage_analysis': {},
            'dependency_analysis': {},
            'performance_impact': 'low',
            'recommended_actions': []
        }
        
        is_stored = field_info.get('stored', False)
        
        # Analyze storage configuration
        if is_stored:
            # Check if database column exists for stored computed field
            db_column_name = field_name
            if field_info['type'] == 'Many2one':
                db_column_name = f"{field_name}_id"
            
            if db_column_name not in db_columns:
                analysis['has_issues'] = True
                analysis['issues'].append('Stored computed field missing database column')
                analysis['storage_analysis']['column_exists'] = False
                analysis['recommended_actions'].append('Add database column for stored computed field')
            else:
                analysis['storage_analysis']['column_exists'] = True
                analysis['storage_analysis']['column_info'] = db_columns[db_column_name]
                
                # Check if column type matches field type
                db_type = db_columns[db_column_name]['type']
                expected_types = self._get_expected_db_types(field_info['type'])
                if expected_types and db_type not in expected_types:
                    analysis['has_issues'] = True
                    analysis['issues'].append(f'Stored computed field type mismatch: {db_type} vs expected {expected_types}')
        else:
            # Non-stored computed field should not have database column
            db_column_name = field_name
            if field_info['type'] == 'Many2one':
                db_column_name = f"{field_name}_id"
            
            if db_column_name in db_columns:
                analysis['has_issues'] = True
                analysis['issues'].append('Non-stored computed field has unnecessary database column')
                analysis['storage_analysis']['unnecessary_column'] = True
                analysis['recommended_actions'].append('Remove database column for non-stored computed field')
        
        # Analyze dependencies
        depends = field_info.get('depends', '')
        if depends:
            dependency_fields = [dep.strip() for dep in depends.split(',') if dep.strip()]
            analysis['dependency_analysis']['depends_fields'] = dependency_fields
            analysis['dependency_analysis']['dependency_count'] = len(dependency_fields)
            
            # Check if dependency fields exist
            missing_dependencies = []
            for dep_field in dependency_fields:
                # Simple check - in real implementation, this would be more sophisticated
                if '.' in dep_field:
                    # Related field dependency
                    base_field = dep_field.split('.')[0]
                    # Get the model info for this model
                    current_model_info = None
                    for orm_model_name, orm_model_info in self.orm_models.items():
                        if orm_model_info['name'] == model_name:
                            current_model_info = orm_model_info
                            break
                    
                    if current_model_info and base_field not in current_model_info['fields']:
                        missing_dependencies.append(dep_field)
                else:
                    # Direct field dependency
                    current_model_info = None
                    for orm_model_name, orm_model_info in self.orm_models.items():
                        if orm_model_info['name'] == model_name:
                            current_model_info = orm_model_info
                            break
                    
                    if current_model_info and dep_field not in current_model_info['fields']:
                        missing_dependencies.append(dep_field)
            
            if missing_dependencies:
                analysis['has_issues'] = True
                analysis['issues'].append(f'Computed field depends on non-existent fields: {missing_dependencies}')
                analysis['dependency_analysis']['missing_dependencies'] = missing_dependencies
                analysis['recommended_actions'].append('Fix or remove invalid dependencies')
            
            # Assess performance impact based on dependency complexity
            if len(dependency_fields) > 5:
                analysis['performance_impact'] = 'high'
                analysis['issues'].append('Computed field has many dependencies - potential performance impact')
            elif len(dependency_fields) > 2:
                analysis['performance_impact'] = 'medium'
        else:
            if field_info.get('computed', False):
                analysis['has_issues'] = True
                analysis['issues'].append('Computed field missing depends declaration')
                analysis['recommended_actions'].append('Add depends declaration for computed field')
        
        return analysis
    
    def _get_expected_db_types(self, field_type: str) -> List[str]:
        """Get expected database types for ORM field type."""
        type_mapping = {
            'Char': ['character varying', 'text'],
            'Text': ['text'],
            'Integer': ['integer', 'bigint'],
            'Float': ['double precision', 'numeric'],
            'Boolean': ['boolean'],
            'Date': ['date'],
            'Datetime': ['timestamp without time zone', 'timestamp with time zone'],
            'Many2one': ['integer', 'bigint'],
            'Selection': ['character varying', 'text']
        }
        return type_mapping.get(field_type, [])
    def run_full_schema_validation(self) -> Dict[str, Any]:
        """Run comprehensive schema validation with Stage 1 integration."""
        if _stage1_available:
            logger.log_validation_event(
                "Starting comprehensive ORM ↔ PostgreSQL schema validation",
                severity=Severity.INFO,
                validation_type="full_schema_validation",
                correlation_id=self.correlation_id
            )
        else:
            logger.info("🚀 Starting comprehensive ORM ↔ PostgreSQL schema validation...")
        
        validation_start_time = time.time()
        
        try:
            # Extract all schema information
            if _stage1_available:
                logger.log_validation_event(
                    "Extracting schema information",
                    severity=Severity.INFO,
                    validation_type="schema_extraction",
                    correlation_id=self.correlation_id
                )
            
            self.extract_orm_models()
            self.extract_database_schema()
            self.extract_ir_model_fields()
            
            # Run all validation checks
            validation_results = {}
            
            # 1. Missing columns detection (enhanced)
            validation_results['missing_columns'] = self.detect_missing_columns()
            
            # 2. Orphan ir.model.fields detection (NEW)
            validation_results['orphan_fields'] = self.detect_orphan_ir_model_fields()
            
            # 3. Type mismatches detection (enhanced)
            validation_results['type_mismatches'] = self.detect_type_mismatches()
            
            # 4. Relational integrity validation (enhanced)
            validation_results['relational_integrity_issues'] = self.validate_relational_integrity()
            
            # 5. Stored computed fields validation (NEW)
            validation_results['stored_computed_field_issues'] = self.validate_stored_computed_fields()
            
            # Calculate validation summary
            self._calculate_validation_summary(validation_results)
            
            # Determine deployment safety (REPORT ONLY - no blocking in Stage 2)
            critical_issues = (
                len(validation_results['missing_columns']) +
                len(validation_results['type_mismatches']) +
                len([issue for issue in validation_results['relational_integrity_issues'] 
                     if 'critical' in str(issue.get('constraint_status', ''))])
            )
            
            # In Stage 2, we REPORT ONLY - never block deployment
            self.validation_results['deployment_safe'] = True  # Always true in monitor mode
            self.validation_results['monitor_mode_active'] = True
            self.validation_results['would_block_deployment'] = critical_issues > 0
            
            if critical_issues > 0:
                self.validation_results['critical_inconsistencies'].append(
                    f"Found {critical_issues} critical schema inconsistencies (MONITOR MODE - not blocking)"
                )
                
                # Create alert for critical issues
                if _stage1_available:
                    create_validation_alert(
                        title="Critical Schema Inconsistencies Detected",
                        message=f"Found {critical_issues} critical schema issues in monitor mode",
                        severity=AlertSeverity.HIGH,
                        validation_type="schema_validation",
                        correlation_id=self.correlation_id,
                        critical_issues=critical_issues,
                        monitor_mode=True
                    )
            
            # Generate comprehensive reports
            self.generate_enhanced_schema_report()
            
            # Log completion
            validation_duration = (time.time() - validation_start_time) * 1000
            
            if _stage1_available:
                logger.log_validation_event(
                    f"Schema validation completed in {validation_duration:.2f}ms",
                    severity=Severity.INFO,
                    validation_type="full_schema_validation",
                    duration_ms=validation_duration,
                    total_issues=sum(len(issues) for issues in validation_results.values()),
                    critical_issues=critical_issues,
                    correlation_id=self.correlation_id
                )
            else:
                logger.info(f"Schema validation completed in {validation_duration:.2f}ms")
            
            return self.validation_results
            
        except Exception as e:
            error_msg = f"Schema validation failed: {e}"
            
            if _stage1_available:
                logger.log_validation_event(
                    error_msg,
                    severity=Severity.ERROR,
                    validation_type="full_schema_validation",
                    error=str(e),
                    correlation_id=self.correlation_id
                )
                
                # Create alert for validation failure
                create_validation_alert(
                    title="Schema Validation Failed",
                    message=error_msg,
                    severity=AlertSeverity.HIGH,
                    validation_type="schema_validation",
                    correlation_id=self.correlation_id,
                    error=str(e)
                )
            else:
                logger.error(error_msg)
            
            # In Stage 2, even failures don't block deployment
            self.validation_results['deployment_safe'] = True
            self.validation_results['validation_failed'] = True
            self.validation_results['critical_inconsistencies'].append(str(e))
            
            return self.validation_results
    
    def _calculate_validation_summary(self, validation_results: Dict[str, List]) -> None:
        """Calculate validation summary statistics."""
        summary = self.validation_results['validation_summary']
        
        # Count totals
        summary['total_models_checked'] = len(self.orm_models)
        summary['total_fields_validated'] = sum(
            len(model_info['fields']) for model_info in self.orm_models.values()
        )
        
        # Count issues
        total_issues = sum(len(issues) for issues in validation_results.values())
        summary['issues_found'] = total_issues
        
        # Count critical issues
        critical_issues = (
            len(validation_results.get('missing_columns', [])) +
            len(validation_results.get('type_mismatches', [])) +
            len([issue for issue in validation_results.get('relational_integrity_issues', [])
                 if 'missing' in str(issue.get('constraint_status', ''))])
        )
        summary['critical_issues'] = critical_issues
        
        # Count warnings
        warning_issues = (
            len(validation_results.get('orphan_fields', [])) +
            len(validation_results.get('stored_computed_field_issues', []))
        )
        summary['warnings_count'] = warning_issues
        
        # Calculate accuracy metrics (simplified for Stage 2)
        if summary['total_fields_validated'] > 0:
            summary['validation_accuracy'] = max(0.0, 
                (summary['total_fields_validated'] - total_issues) / summary['total_fields_validated']
            )
        else:
            summary['validation_accuracy'] = 1.0
        
        # Estimate false positive rate (placeholder - would need historical data)
        summary['false_positive_rate'] = min(0.05, total_issues * 0.01)  # Simplified estimation
    
    def generate_enhanced_schema_report(self):
        """Generate comprehensive schema validation report with detailed analysis."""
        report_path = self.module_path / "deployment" / "schema_validation_report.json"
        report_path.parent.mkdir(exist_ok=True)
        
        # Add metadata to results
        self.validation_results['metadata'] = {
            'validation_timestamp': datetime.now(timezone.utc).isoformat(),
            'validation_duration_ms': (time.time() - self.start_time) * 1000 if hasattr(self, 'start_time') else 0,
            'correlation_id': getattr(self, 'correlation_id', None),
            'stage': 'Stage 2 - Passive Validation Mode',
            'monitor_mode': True,
            'enforcement_mode': False,
            'schema_guard_version': '2.0.0',
            'total_models_analyzed': len(self.orm_models),
            'total_tables_analyzed': len(self.db_schema),
            'total_ir_model_fields': sum(len(fields) for fields in self.ir_model_fields.values())
        }
        
        # Save JSON report
        with open(report_path, 'w', encoding='utf-8') as f:
            json.dump(self.validation_results, f, indent=2, default=str)
        
        # Generate enhanced human-readable report
        text_report_path = self.module_path / "deployment" / "schema_validation_report.txt"
        with open(text_report_path, 'w', encoding='utf-8') as f:
            f.write("HAGBES FLEET ORM ↔ POSTGRESQL SCHEMA VALIDATION REPORT\n")
            f.write("=" * 70 + "\n")
            f.write(f"Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}\n")
            f.write(f"Stage: Stage 2 - Passive Validation Mode (MONITOR ONLY)\n")
            f.write(f"Correlation ID: {getattr(self, 'correlation_id', 'N/A')}\n")
            f.write("=" * 70 + "\n\n")
            
            # Validation Summary
            summary = self.validation_results['validation_summary']
            f.write("VALIDATION SUMMARY\n")
            f.write("-" * 20 + "\n")
            f.write(f"Models Analyzed: {summary['total_models_checked']}\n")
            f.write(f"Fields Validated: {summary['total_fields_validated']}\n")
            f.write(f"Issues Found: {summary['issues_found']}\n")
            f.write(f"Critical Issues: {summary['critical_issues']}\n")
            f.write(f"Warnings: {summary['warnings_count']}\n")
            f.write(f"Validation Accuracy: {summary['validation_accuracy']:.2%}\n")
            f.write(f"Estimated False Positive Rate: {summary['false_positive_rate']:.2%}\n")
            f.write("\n")
            
            # Deployment Status
            f.write("DEPLOYMENT STATUS\n")
            f.write("-" * 17 + "\n")
            f.write(f"Monitor Mode Active: ✅ YES\n")
            f.write(f"Would Block Deployment: {'❌ YES' if self.validation_results.get('would_block_deployment', False) else '✅ NO'}\n")
            f.write(f"Actual Deployment Blocking: ✅ DISABLED (Stage 2 Monitor Mode)\n")
            f.write("\n")
            
            # Missing Columns
            if self.validation_results['missing_columns']:
                f.write("MISSING DATABASE COLUMNS\n")
                f.write("-" * 25 + "\n")
                for issue in self.validation_results['missing_columns']:
                    f.write(f"❌ {issue['model']}.{issue['field']} → {issue['table']}.{issue['db_column']}\n")
                    f.write(f"   Type: {issue['field_type']}, Required: {issue['required']}\n")
                    f.write(f"   Impact: {issue['impact_analysis']['severity'].upper()}\n")
                    f.write(f"   Migration: {issue['migration_suggestion']['sql']}\n")
                    f.write("\n")
            
            # Orphan Fields
            if self.validation_results['orphan_fields']:
                f.write("ORPHAN IR.MODEL.FIELDS RECORDS\n")
                f.write("-" * 30 + "\n")
                for issue in self.validation_results['orphan_fields']:
                    f.write(f"⚠️  {issue['model']}.{issue['field']} (ID: {issue['ir_model_field_id']})\n")
                    f.write(f"   Issue: {issue['issue']}\n")
                    f.write(f"   Recommendation: {issue['cleanup_recommendation']}\n")
                    f.write("\n")
            
            # Type Mismatches
            if self.validation_results['type_mismatches']:
                f.write("FIELD TYPE MISMATCHES\n")
                f.write("-" * 21 + "\n")
                for issue in self.validation_results['type_mismatches']:
                    f.write(f"⚠️  {issue['model']}.{issue['field']}: ORM={issue['orm_type']}, DB={issue['db_type']}\n")
                    f.write(f"   Expected: {issue['expected_db_types']}\n")
                    f.write(f"   Migration Safe: {issue['migration_safe']}\n")
                    f.write(f"   Severity: {issue['mismatch_analysis']['severity'].upper()}\n")
                    f.write("\n")
            
            # Relational Integrity Issues
            if self.validation_results['relational_integrity_issues']:
                f.write("RELATIONAL INTEGRITY ISSUES\n")
                f.write("-" * 28 + "\n")
                for issue in self.validation_results['relational_integrity_issues']:
                    f.write(f"⚠️  {issue['model']}.{issue['field']} → {issue['related_model']}\n")
                    f.write(f"   Status: {issue['constraint_status'].upper()}\n")
                    for problem in issue['issues']:
                        f.write(f"   - {problem}\n")
                    f.write("\n")
            
            # Stored Computed Field Issues
            if self.validation_results['stored_computed_field_issues']:
                f.write("STORED COMPUTED FIELD ISSUES\n")
                f.write("-" * 29 + "\n")
                for issue in self.validation_results['stored_computed_field_issues']:
                    f.write(f"⚠️  {issue['model']}.{issue['field']} (Stored: {issue['stored']})\n")
                    for problem in issue['issues']:
                        f.write(f"   - {problem}\n")
                    f.write(f"   Performance Impact: {issue['performance_impact'].upper()}\n")
                    f.write("\n")
            
            # Critical Inconsistencies
            if self.validation_results['critical_inconsistencies']:
                f.write("CRITICAL INCONSISTENCIES\n")
                f.write("-" * 24 + "\n")
                for issue in self.validation_results['critical_inconsistencies']:
                    f.write(f"🚨 {issue}\n")
                f.write("\n")
            
            # Recommendations
            f.write("RECOMMENDATIONS\n")
            f.write("-" * 15 + "\n")
            if summary['critical_issues'] > 0:
                f.write("1. Address critical schema inconsistencies before production deployment\n")
                f.write("2. Run database migrations to add missing columns\n")
                f.write("3. Fix type mismatches with appropriate data conversion\n")
            if summary['warnings_count'] > 0:
                f.write("4. Clean up orphan ir.model.fields records\n")
                f.write("5. Review stored computed field configurations\n")
            f.write("6. Monitor validation accuracy and tune thresholds as needed\n")
            f.write("7. Review false positive rate and adjust validation rules\n")
        
        if _stage1_available:
            logger.log_validation_event(
                f"Enhanced schema validation report generated",
                severity=Severity.INFO,
                validation_type="report_generation",
                report_path=str(text_report_path),
                correlation_id=self.correlation_id
            )
        else:
            logger.info(f"Enhanced schema validation report generated: {text_report_path}")


# Conditional class definition for Stage 1 integration
if _stage1_available:
    class SchemaGuardValidator(BaseValidator):
        """
        Schema Guard validator for integration with Stage 1 validation engine.
        
        Provides schema validation as a pluggable validator component
        that can be orchestrated by the validation engine.
        """
        
        def __init__(self, module_path: str, db_config: Dict[str, str]):
            """
            Initialize schema guard validator.
            
            Args:
                module_path: Path to the hagbes_fleet module
                db_config: Database configuration
            """
            super().__init__(
                name="schema_guard",
                description="ORM ↔ PostgreSQL schema synchronization validator"
            )
            self.module_path = module_path
            self.db_config = db_config
            self.set_timeout(120)  # 2 minutes timeout for schema validation
        
        def validate(self, context: Dict[str, Any]) -> ValidationResult:
            """
            Perform schema validation.
            
            Args:
                context: Validation context containing correlation_id and other data
                
            Returns:
                ValidationResult: Schema validation result
            """
            start_time = time.time()
            correlation_id = context.get('correlation_id')
            
            try:
                # Create schema guard instance
                guard = SchemaGuard(self.module_path, self.db_config)
                guard.set_correlation_id(correlation_id)
                
                # Run validation
                results = guard.run_full_schema_validation()
                
                # Determine result severity based on issues found
                total_issues = results['validation_summary']['issues_found']
                critical_issues = results['validation_summary']['critical_issues']
                
                if critical_issues > 0:
                    severity = ValidationSeverity.ERROR
                    message = f"Schema validation found {critical_issues} critical issues and {total_issues - critical_issues} warnings"
                elif total_issues > 0:
                    severity = ValidationSeverity.WARNING
                    message = f"Schema validation found {total_issues} warnings"
                else:
                    severity = ValidationSeverity.INFO
                    message = "Schema validation passed - no issues found"
                
                execution_time = (time.time() - start_time) * 1000
                
                return self._create_result(
                    ValidationStatus.COMPLETED,
                    severity,
                    message,
                    {
                        'validation_summary': results['validation_summary'],
                        'missing_columns_count': len(results['missing_columns']),
                        'orphan_fields_count': len(results['orphan_fields']),
                        'type_mismatches_count': len(results['type_mismatches']),
                        'relational_issues_count': len(results['relational_integrity_issues']),
                        'computed_field_issues_count': len(results['stored_computed_field_issues']),
                        'monitor_mode': results.get('monitor_mode_active', True),
                        'would_block_deployment': results.get('would_block_deployment', False),
                        'report_generated': True
                    },
                    execution_time,
                    correlation_id
                )
                
            except Exception as e:
                execution_time = (time.time() - start_time) * 1000
                
                return self._create_result(
                    ValidationStatus.FAILED,
                    ValidationSeverity.ERROR,
                    f"Schema validation failed: {e}",
                    {
                        'error': str(e),
                        'error_type': type(e).__name__,
                        'monitor_mode': True,
                        'validation_failed': True
                    },
                    execution_time,
                    correlation_id
                )
else:
    # Placeholder class when Stage 1 infrastructure is not available
    class SchemaGuardValidator:
        """Placeholder SchemaGuardValidator for standalone execution."""
        def __init__(self, module_path: str, db_config: Dict[str, str]):
            self.module_path = module_path
            self.db_config = db_config


def main():
    """Main schema validation entry point with Stage 1 integration."""
    if len(sys.argv) != 3:
        print("Usage: python schema_guard.py <module_path> <db_config_json>")
        sys.exit(1)
    
    module_path = sys.argv[1]
    db_config = json.loads(sys.argv[2])
    
    # Check if Stage 1 infrastructure is available
    if _stage1_available:
        # Use validation engine integration
        from ..safeguards.validation_engine import execute_validation
        
        # Register schema guard validator
        validator = SchemaGuardValidator(module_path, db_config)
        
        # Execute validation through engine
        context = {
            'module_path': module_path,
            'db_config': db_config,
            'correlation_id': f"schema_validation_{int(time.time())}"
        }
        
        summary = execute_validation(context, ['schema_guard'])
        
        if summary.overall_status == ValidationStatus.COMPLETED:
            print("🎉 SCHEMA VALIDATION COMPLETED - Monitor mode active")
            sys.exit(0)
        else:
            print("🚫 SCHEMA VALIDATION ISSUES DETECTED - Check reports for details")
            sys.exit(1)
    else:
        # Fallback to standalone execution
        guard = SchemaGuard(module_path, db_config)
        results = guard.run_full_schema_validation()
        
        if results.get('validation_failed', False):
            print("🚫 SCHEMA VALIDATION FAILED - Check logs for details")
            sys.exit(1)
        else:
            print("🎉 SCHEMA VALIDATION COMPLETED - Monitor mode active")
            sys.exit(0)


if __name__ == "__main__":
    main()