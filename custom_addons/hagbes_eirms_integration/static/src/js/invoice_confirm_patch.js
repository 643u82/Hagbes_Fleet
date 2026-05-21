import { registry } from "@web/core/registry";
import { rpc } from "@web/core/network/rpc";

icp = self.env["ir.config.parameter"].sudo();
clientId = icp.get_param("mor.clientId");
clientSecret = icp.get_param("mor.clientSecret");
apikey = icp.get_param("mor.apikey");
tin = icp.get_param("tin");

async function morLogin(env, action) {
  try {
    const result = await rpc("mor/api/login", {
      clientId: clientId,
      clientSecret: clientSecret,
      apikey: apikey,
      tin: tin,
    });
    console.log("sending to mor", tin);
    if (result.success) {
      console.log("API response: ", result.response);
      env.services.notification.add("Logged in successfully", {
        type: "success",
      });
    } else {
      throw new Error(result.error || "Unkown error");
    }
  } catch (error) {
    console.error("Erro sending");
    env.services.notification.add("Failed to login ", { type: "danger" });
  }
}
registry.category("actions").add("");
