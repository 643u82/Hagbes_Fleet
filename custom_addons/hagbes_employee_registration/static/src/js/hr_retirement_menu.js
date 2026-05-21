odoo.define('employee_registration.hr_retirement_menu', function (require) {
    "use strict";

    var Menu = require('web.Menu');

    Menu.include({
        start: function () {
            this._super.apply(this, arguments);
            this._updateRetirementBadge();
        },

        _updateRetirementBadge: function () {
            var self = this;
            this._rpc({
                model: 'employee.retirement',
                method: '_get_retirement_count',
                args: [],
            }).then(function (count) {
                if (count > 0) {
                    // Select the retirement menu item by custom data attribute
                    var retirementMenu = self.$el.find('[data-menu="retirement_menu"]');

                    if (retirementMenu.length) {
                        // Remove any existing badge
                        retirementMenu.find('.badge').remove();

                        // Append the new badge
                        retirementMenu.append('<span class="badge">' + count + '</span>');
                    }
                }
            });
        },
    });
});
