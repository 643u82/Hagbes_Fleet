# -*- coding: utf-8 -*-

# CONSOLIDATED Hagbes Fleet Models - Single Source of Truth
# Total: 8 core models only

# Core Business Layer
from . import fleet_requisition
from . import fleet_requisition_reject_wizard

# Execution Layer  
from . import fleet_trip

# Asset Layer
from . import fleet_vehicle
from . import fleet_maintenance

# Supporting Models
from . import fleet_config_settings
from . import hr_employee
