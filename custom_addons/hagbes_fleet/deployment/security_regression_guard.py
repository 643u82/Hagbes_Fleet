#!/usr/bin/env python3
"""
HAGBES FLEET SECURITY REGRESSION PROTECTION
===========================================

Prevents future permission leaks and security regressions by validating:
- Regular users cannot access management reports
- Department managers only see department-level approvals
- Property approvals restricted to property officers
- FMO approvals restricted to FMO officers
- Menu visibility matches security groups
"""

import os
import sys
import json
import logging
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict, List, Tuple, Any, Optional, Set
import re

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class SecurityRegressionGuard:
    """Security regression protection system."""
    
    def __init__(self, module_path: str):
        self.module_path = Path(module_path)
        self.validation_results = {
            'management_reports_protected': False,
            'department_isolation_enforced': False,
            'property_approvals_restricted': False,
            'fmo_approvals_restricted': False,
            'menu_visibility_correct': False,
            'access_rules_complete': False,
            'security_violations': [],
            'warnings': [],
            'security_protected': False
        }
        
        # Security model definition
        self.security_model = {
            'groups': {
                'group_fleet_requester': {
                    'level': 1,
                    'description': 'Basic requester - can only create and view own requests',
                    'allowed_models': ['fleet.requisition'],
                    'restricted_models': ['hagbes.fleet.allocation', 'hagbes.fleet.discrepancy'],
                    'allowed_menus': ['menu_fleet_requisitions']
                },
                'group_dept_manager': {
                    'level': 2,
                    'description': 'Department manager - can approve department requests',
                    'allowed_models': ['fleet.requisition', 'fleet.trip'],
                    'restricted_models': ['hagbes.fleet.allocation', 'hagbes.fleet.discrepancy'],
                    'allowed_menus': ['menu_fleet_requisitions', 'menu_fleet_dept_approvals']
                },
                'group_fmo': {
                    'level': 3,
                    'description': 'FMO officer - operational fleet management',
                    'allowed_models': ['*'],  # All models
                    'restricted_models': [],
                    'allowed_menus': ['*']  # Most menus
                },
                'group_fleet_manager': {
                    'level': 4,
                    'description': 'Fleet manager - full oversight',
                    'allowed_models': ['*'],
                    'restricted_models': [],
                    'allowed_menus': ['*']
                },
                'group_fleet_admin': {
                    'level': 5,
                    'description': 'Fleet admin - system control',
                    'allowed_models': ['*'],
                    'restricted_models': [],
                    'allowed_menus': ['*']
                }
            },
            'sensitive_operations': [
                'fleet_requisition_report',
                'fleet_trip_summary_report',
                'fleet_discrepancy_analysis',
                'fleet_allocation_management'
            ]
        }
    
    def validate_management_reports_protection(self) -> bool:
        """Ensure regular users cannot access management reports."""
        logger.info("🔍 Validating management reports protection...")
        
        reports_dir = self.module_path / "reports"
        if not reports_dir.exists():
            self.validation_results['warnings'].append("No reports directory found")
            return True
        
        violations = []
        
        for report_file in reports_dir.glob("*.xml"):
            try:
                tree = ET.parse(report_file)
                root = tree.getroot()
                
                # Find report definitions
                for report in root.findall(".//record[@model='ir.actions.report']"):
                    report_name = report.find(".//field[@name='name']")
                    groups_field = report.find(".//field[@name='groups_id']")
                    
                    if report_name is not None:
                        report_title = report_name.text
                        
                        # Check if management reports have proper group restrictions
                        if any(keyword in report_title.lower() for keyword in ['summary', 'analysis', 'management']):
                            if groups_field is None:
                                violations.append({
                                    'type': 'unrestricted_management_report',
                                    'report': report_title,
                                    'file': str(report_file),
                                    'issue': 'Management report accessible to all users'
                                })
                            else:
                                # Check if restricted to appropriate groups
                                groups_ref = groups_field.get('ref', '')
                                if 'group_fleet_requester' in groups_ref:
                                    violations.append({
                                        'type': 'overprivileged_report_access',
                                        'report': report_title,
                                        'file': str(report_file),
                                        'issue': 'Management report accessible to basic requesters'
                                    })
                
            except Exception as e:
                self.validation_results['warnings'].append(f"Could not parse report file {report_file}: {e}")
        
        if violations:
            self.validation_results['security_violations'].extend(violations)
            logger.warning(f"Found {len(violations)} management report security violations")
            return False
        
        logger.info("✅ Management reports protection validated")
        return True
    
    def validate_department_isolation(self) -> bool:
        """Ensure department managers only see department-level approvals."""
        logger.info("🔍 Validating department isolation...")
        
        # Check record rules for department isolation
        security_rules_file = self.module_path / "security" / "fleet_requisition_rules.xml"
        if not security_rules_file.exists():
            self.validation_results['security_violations'].append({
                'type': 'missing_department_isolation',
                'issue': 'No department isolation rules found'
            })
            return False
        
        try:
            tree = ET.parse(security_rules_file)
            root = tree.getroot()
            
            # Look for department manager record rules
            dept_manager_rules = []
            for rule in root.findall(".//record[@model='ir.rule']"):
                groups_field = rule.find(".//field[@name='groups']")
                domain_field = rule.find(".//field[@name='domain_force']")
                
                if groups_field is not None and 'group_dept_manager' in groups_field.get('eval', ''):
                    dept_manager_rules.append({
                        'domain': domain_field.text if domain_field is not None else '',
                        'rule_id': rule.get('id', '')
                    })
            
            # Validate department isolation rules exist
            department_isolation_found = False
            for rule in dept_manager_rules:
                if 'department_id' in rule['domain'] or 'request_by' in rule['domain']:
                    department_isolation_found = True
                    break
            
            if not department_isolation_found:
                self.validation_results['security_violations'].append({
                    'type': 'missing_department_isolation_rule',
                    'issue': 'Department managers can see all requisitions, not just their department'
                })
                return False
            
            logger.info("✅ Department isolation validated")
            return True
            
        except Exception as e:
            self.validation_results['security_violations'].append({
                'type': 'department_isolation_validation_error',
                'issue': f"Could not validate department isolation: {e}"
            })
            return False
    
    def validate_property_approval_restrictions(self) -> bool:
        """Ensure property approvals restricted to property officers."""
        logger.info("🔍 Validating property approval restrictions...")
        
        requisition_model_path = self.module_path / "models" / "fleet_requisition.py"
        if not requisition_model_path.exists():
            return False
        
        try:
            with open(requisition_model_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Check permission computation for property approval
            permission_pattern = r'can_property_approve\s*=.*?(?=\n\s*\w+\s*=|\n\s*$)'
            permission_match = re.search(permission_pattern, content, re.DOTALL)
            
            if not permission_match:
                self.validation_results['security_violations'].append({
                    'type': 'missing_property_approval_permission',
                    'issue': 'Property approval permission field not found'
                })
                return False
            
            permission_logic = permission_match.group(0)
            
            # Validate that only fleet managers can approve property stage
            if 'is_fleet_manager' not in permission_logic and 'group_fleet_manager' not in permission_logic:
                self.validation_results['security_violations'].append({
                    'type': 'unrestricted_property_approval',
                    'issue': 'Property approval not restricted to fleet managers'
                })
                return False
            
            # Validate state check
            if "state == 'dept_approved'" not in permission_logic:
                self.validation_results['security_violations'].append({
                    'type': 'missing_property_approval_state_check',
                    'issue': 'Property approval does not check for dept_approved state'
                })
                return False
            
            logger.info("✅ Property approval restrictions validated")
            return True
            
        except Exception as e:
            self.validation_results['security_violations'].append({
                'type': 'property_approval_validation_error',
                'issue': f"Could not validate property approval restrictions: {e}"
            })
            return False
    
    def validate_fmo_approval_restrictions(self) -> bool:
        """Ensure FMO approvals restricted to FMO officers."""
        logger.info("🔍 Validating FMO approval restrictions...")
        
        requisition_model_path = self.module_path / "models" / "fleet_requisition.py"
        if not requisition_model_path.exists():
            return False
        
        try:
            with open(requisition_model_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Check permission computation for FMO approval
            permission_pattern = r'can_fmo_approve\s*=.*?(?=\n\s*\w+\s*=|\n\s*$)'
            permission_match = re.search(permission_pattern, content, re.DOTALL)
            
            if not permission_match:
                self.validation_results['security_violations'].append({
                    'type': 'missing_fmo_approval_permission',
                    'issue': 'FMO approval permission field not found'
                })
                return False
            
            permission_logic = permission_match.group(0)
            
            # Validate that only FMO officers can approve FMO stage
            if 'is_fmo' not in permission_logic and 'group_fmo' not in permission_logic:
                self.validation_results['security_violations'].append({
                    'type': 'unrestricted_fmo_approval',
                    'issue': 'FMO approval not restricted to FMO officers'
                })
                return False
            
            # Validate state check
            if "state == 'property_approved'" not in permission_logic:
                self.validation_results['security_violations'].append({
                    'type': 'missing_fmo_approval_state_check',
                    'issue': 'FMO approval does not check for property_approved state'
                })
                return False
            
            logger.info("✅ FMO approval restrictions validated")
            return True
            
        except Exception as e:
            self.validation_results['security_violations'].append({
                'type': 'fmo_approval_validation_error',
                'issue': f"Could not validate FMO approval restrictions: {e}"
            })
            return False
    
    def validate_menu_visibility(self) -> bool:
        """Ensure menu visibility matches security groups."""
        logger.info("🔍 Validating menu visibility...")
        
        menu_file = self.module_path / "views" / "fleet_menu.xml"
        if not menu_file.exists():
            self.validation_results['security_violations'].append({
                'type': 'missing_menu_file',
                'issue': 'Menu file not found'
            })
            return False
        
        try:
            tree = ET.parse(menu_file)
            root = tree.getroot()
            
            violations = []
            
            # Check each menu item
            for menuitem in root.findall(".//menuitem"):
                menu_id = menuitem.get('id', '')
                menu_name = menuitem.get('name', '')
                groups = menuitem.get('groups', '')
                
                # Validate sensitive menus have proper restrictions
                sensitive_menus = [
                    'allocations', 'discrepancies', 'reports', 'configuration'
                ]
                
                for sensitive in sensitive_menus:
                    if sensitive.lower() in menu_name.lower():
                        if not groups:
                            violations.append({
                                'type': 'unrestricted_sensitive_menu',
                                'menu': menu_name,
                                'menu_id': menu_id,
                                'issue': 'Sensitive menu accessible to all users'
                            })
                        elif 'group_fleet_requester' in groups:
                            violations.append({
                                'type': 'overprivileged_menu_access',
                                'menu': menu_name,
                                'menu_id': menu_id,
                                'issue': 'Sensitive menu accessible to basic requesters'
                            })
                
                # Validate approval menu restrictions
                if 'approval' in menu_name.lower():
                    if 'group_dept_manager' not in groups:
                        violations.append({
                            'type': 'incorrect_approval_menu_access',
                            'menu': menu_name,
                            'menu_id': menu_id,
                            'issue': 'Approval menu not restricted to department managers'
                        })
            
            if violations:
                self.validation_results['security_violations'].extend(violations)
                logger.warning(f"Found {len(violations)} menu visibility violations")
                return False
            
            logger.info("✅ Menu visibility validated")
            return True
            
        except Exception as e:
            self.validation_results['security_violations'].append({
                'type': 'menu_visibility_validation_error',
                'issue': f"Could not validate menu visibility: {e}"
            })
            return False
    
    def validate_access_rules_completeness(self) -> bool:
        """Validate access rules are complete and properly restrictive."""
        logger.info("🔍 Validating access rules completeness...")
        
        access_file = self.module_path / "security" / "ir.model.access.csv"
        if not access_file.exists():
            self.validation_results['security_violations'].append({
                'type': 'missing_access_rules',
                'issue': 'Access rules file not found'
            })
            return False
        
        try:
            with open(access_file, 'r', encoding='utf-8') as f:
                access_content = f.read()
            
            violations = []
            
            # Parse access rules
            lines = access_content.strip().split('\n')
            access_rules = []
            
            for line in lines[1:]:  # Skip header
                if line.strip():
                    parts = line.split(',')
                    if len(parts) >= 7:
                        access_rules.append({
                            'id': parts[0],
                            'name': parts[1],
                            'model': parts[2],
                            'group': parts[3],
                            'read': parts[4] == '1',
                            'write': parts[5] == '1',
                            'create': parts[6] == '1',
                            'unlink': parts[7] == '1' if len(parts) > 7 else False
                        })
            
            # Validate sensitive models have proper restrictions
            sensitive_models = [
                'hagbes.fleet.allocation',
                'hagbes.fleet.discrepancy',
                'hagbes.fleet.trip.log'
            ]
            
            for model in sensitive_models:
                model_rules = [rule for rule in access_rules if model in rule['model']]
                
                # Check if requesters have access to sensitive models
                requester_rules = [rule for rule in model_rules if 'group_fleet_requester' in rule['group']]
                for rule in requester_rules:
                    if rule['write'] or rule['create'] or rule['unlink']:
                        violations.append({
                            'type': 'overprivileged_requester_access',
                            'model': model,
                            'rule_id': rule['id'],
                            'issue': 'Requesters have write/create/delete access to sensitive model'
                        })
                
                # Check if department managers have inappropriate access
                dept_manager_rules = [rule for rule in model_rules if 'group_dept_manager' in rule['group']]
                for rule in dept_manager_rules:
                    if rule['write'] or rule['create'] or rule['unlink']:
                        violations.append({
                            'type': 'overprivileged_dept_manager_access',
                            'model': model,
                            'rule_id': rule['id'],
                            'issue': 'Department managers have write/create/delete access to operational model'
                        })
            
            # Validate all required models have access rules
            required_models = [
                'fleet.requisition',
                'hagbes.fleet.allocation',
                'hagbes.fleet.trip.log',
                'hagbes.fleet.discrepancy'
            ]
            
            for model in required_models:
                model_rules = [rule for rule in access_rules if model.replace('.', '_') in rule['model']]
                if not model_rules:
                    violations.append({
                        'type': 'missing_model_access_rules',
                        'model': model,
                        'issue': 'No access rules found for required model'
                    })
            
            if violations:
                self.validation_results['security_violations'].extend(violations)
                logger.warning(f"Found {len(violations)} access rule violations")
                return False
            
            logger.info("✅ Access rules completeness validated")
            return True
            
        except Exception as e:
            self.validation_results['security_violations'].append({
                'type': 'access_rules_validation_error',
                'issue': f"Could not validate access rules: {e}"
            })
            return False
    
    def run_full_security_validation(self) -> Dict[str, Any]:
        """Run complete security regression validation."""
        logger.info("🚀 Starting security regression protection validation...")
        
        # Run all security validation checks
        validations = [
            ('management_reports_protected', self.validate_management_reports_protection),
            ('department_isolation_enforced', self.validate_department_isolation),
            ('property_approvals_restricted', self.validate_property_approval_restrictions),
            ('fmo_approvals_restricted', self.validate_fmo_approval_restrictions),
            ('menu_visibility_correct', self.validate_menu_visibility),
            ('access_rules_complete', self.validate_access_rules_completeness)
        ]
        
        all_passed = True
        for validation_name, validation_func in validations:
            try:
                result = validation_func()
                self.validation_results[validation_name] = result
                if not result:
                    all_passed = False
            except Exception as e:
                logger.error(f"Security validation {validation_name} failed with exception: {e}")
                self.validation_results[validation_name] = False
                self.validation_results['security_violations'].append({
                    'type': f'{validation_name}_exception',
                    'issue': str(e)
                })
                all_passed = False
        
        # Final security decision
        self.validation_results['security_protected'] = all_passed and len(self.validation_results['security_violations']) == 0
        
        # Generate security report
        self.generate_security_report()
        
        return self.validation_results
    
    def generate_security_report(self):
        """Generate security validation report."""
        report_path = self.module_path / "deployment" / "security_validation_report.json"
        report_path.parent.mkdir(exist_ok=True)
        
        with open(report_path, 'w', encoding='utf-8') as f:
            json.dump(self.validation_results, f, indent=2)
        
        # Generate human-readable report
        text_report_path = self.module_path / "deployment" / "security_validation_report.txt"
        with open(text_report_path, 'w', encoding='utf-8') as f:
            f.write("HAGBES FLEET SECURITY REGRESSION PROTECTION REPORT\n")
            f.write("=" * 55 + "\n\n")
            
            f.write("SECURITY VALIDATION RESULTS:\n")
            for check, result in self.validation_results.items():
                if check not in ['security_violations', 'warnings', 'security_protected']:
                    status = "✅ PASS" if result else "❌ FAIL"
                    f.write(f"  {check}: {status}\n")
            
            f.write(f"\nSECURITY PROTECTED: {'✅ YES' if self.validation_results['security_protected'] else '❌ NO'}\n\n")
            
            if self.validation_results['security_violations']:
                f.write("SECURITY VIOLATIONS:\n")
                for violation in self.validation_results['security_violations']:
                    f.write(f"  ❌ {violation['type']}: {violation['issue']}\n")
                f.write("\n")
            
            if self.validation_results['warnings']:
                f.write("WARNINGS:\n")
                for warning in self.validation_results['warnings']:
                    f.write(f"  ⚠️  {warning}\n")
            
            f.write("\nSECURITY MODEL:\n")
            for group, config in self.security_model['groups'].items():
                f.write(f"  {group} (Level {config['level']}): {config['description']}\n")
        
        logger.info(f"Security validation report generated: {text_report_path}")


def main():
    """Main security validation entry point."""
    if len(sys.argv) != 2:
        print("Usage: python security_regression_guard.py <module_path>")
        sys.exit(1)
    
    module_path = sys.argv[1]
    guard = SecurityRegressionGuard(module_path)
    results = guard.run_full_security_validation()
    
    if results['security_protected']:
        logger.info("🎉 SECURITY PROTECTED - All validations passed")
        sys.exit(0)
    else:
        logger.error("🚫 SECURITY COMPROMISED - Violations detected")
        logger.error(f"Security violations: {len(results['security_violations'])}")
        for violation in results['security_violations']:
            logger.error(f"  ❌ {violation['type']}: {violation['issue']}")
        sys.exit(1)


if __name__ == "__main__":
    main()