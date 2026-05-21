/** @odoo-module **/

import { registry } from "@web/core/registry";
import { rpc } from "@web/core/network/rpc";

async function getFsNumber(env, action) {
  try {
    // 🔹 1. Call LOCAL PEDS
    const posUrl =
      "http://localhost:2010/PEDS/API/HoldSalesService/GetPaidStatusList";

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
    console.log("FS Number Response:", result);

    if (!result.Success || !result.Content?.length) {
      throw new Error(result.Message || "FS number not available");
    }

    // 🔹 2. Extract FS data
    const content = result.Content[0];
    const salesInfo = content.SalesInfo[0];

    const fsNumber = salesInfo.FsInvoiceNo;
    const invoiceNumber = salesInfo.InvoiceNumber;
    const ejNumber = salesInfo.EJNo;
    const machineId = salesInfo.MachineID;

    // 🔹 3. Register in Odoo (POST + SAVE)
    const registerResult = await rpc("/pos/register_fs_number", {
      invoice_number: invoiceNumber,
      fs_number: fsNumber,
      ej_number: ejNumber,
      machine_id: machineId,
    });

    if (!registerResult.success) {
      throw new Error(registerResult.error);
    }

    env.services.notification.add(
      `Invoice posted successfully (FS: ${fsNumber})`,
      { type: "success" }
    );

    // 🔹 Refresh view
    window.location.reload();
  } catch (error) {
    console.error("FS Number flow failed:", error);

    env.services.notification.add(
      error.message || "Failed to fetch FS Number",
      { type: "danger" }
    );
  }
}

registry.category("actions").add("get_fs_number", getFsNumber);
