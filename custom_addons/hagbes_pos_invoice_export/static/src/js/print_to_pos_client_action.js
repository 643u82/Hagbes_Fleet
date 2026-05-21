/** @odoo-module **/

import { registry } from "@web/core/registry";
import { rpc } from "@web/core/network/rpc";

async function printToPos(env, action) {
  console.log("POS DATA", JSON.stringify(action.data));
  try {
    const posUrl = "http://localhost:2010/PEDS/API/HoldSalesService/Add";
    const base64Auth = btoa("pedsadmin:lock@peds");

    const response = await fetch(posUrl, {
      method: "POST",
      headers: {
        Authorization: `Basic ${base64Auth}`,
        "Content-Type": "application/json",
        Accept: "application/json",
      },
      body: JSON.stringify(action.data),
    });

    const result = await response.json();
    console.log("POS Response:", result);

    if (!result.Success) {
      throw new Error(result.Message || "POS Error");
    }

    // ✅ Tell Odoo: printing succeeded
    await rpc("/pos/set_waiting_fs_number", {
      invoice_id: action.context.active_id,
    });

    env.services.notification.add(
      "Printed successfully. Waiting for FS Number…",
      { type: "success" }
    );
    window.location.reload();
  } catch (error) {
    console.error("Error sending to POS:", error);
    env.services.notification.add("Failed to send invoice to POS", {
      type: "danger",
    });
  }
}

registry.category("actions").add("print_to_pos", printToPos);
