/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { CalendarRenderer } from "@web/views/calendar/calendar_renderer";

patch(CalendarRenderer, {
    
    _getEventClass(event) {
        let base_class = super._getEventClass(...arguments);
        if (event.model === "resource.calendar.leaves") {
            base_class += " o-public-holiday";
        }
        return base_class;
    },

    _renderEventElement(event) {
        const el = super._renderEventElement(...arguments);
        if (event.model === "resource.calendar.leaves") {
            el.setAttribute("title", event.title || event.name);
        }
        return el;
    },
});
