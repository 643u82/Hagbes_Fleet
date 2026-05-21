odoo.define('customized_inventory.hide_return_button', function (require) {
    "use strict";

    var FormController = require('web.FormController');
    console.log("hide_return_button loaded");

    FormController.include({
        renderButtons: function ($node) {
            this._super.apply(this, arguments);

            if (this.modelName === 'stock.picking' && this.renderer.state.data) {
                var picking_type = this.renderer.state.data.picking_type_code;
                if (picking_type === 'exhibition_receive' || picking_type === 'exhibition_request') {
                    // Hide any button with string 'Return'
                    this.$buttons.find('button.o_form_button:contains("Return")').hide();
                }
            }
        },
    });
});
