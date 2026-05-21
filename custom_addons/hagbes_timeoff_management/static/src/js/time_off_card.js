/** @odoo-module **/

import { registry } from "@web/core/registry";

console.log("custom_timeoff: time_off_card.js loaded");

registry.category("hr_holidays.Dashboard").add("hide_pending_requests", {
    async start(dashboard) {
        console.log("custom_timeoff: dashboard start called", dashboard && !!dashboard.loadDashboardData);
       
        const originalLoad = dashboard.loadDashboardData.bind(dashboard);

        // Patch 
        dashboard.loadDashboardData = async function (...args) {
            await originalLoad(...args);

            try {
               
                console.log("custom_timeoff: dashboard holidays before filter", this.state.holidays.map(c=>c.title||c.name));
                this.state.holidays = this.state.holidays.filter(
                    (card) => (card.title || card.name || "").toString().trim() !== "Pending Requests"
                );
                console.log("custom_timeoff: dashboard holidays after filter", this.state.holidays.map(c=>c.title||c.name));
            } catch (e) {
                console.error("custom_timeoff: error filtering dashboard holidays", e);
            }

            // Re-render dashboard
            this.render(true);
        };

        
        try {
            if (dashboard.state && Array.isArray(dashboard.state.holidays) && dashboard.state.holidays.length) {
                dashboard.state.holidays = dashboard.state.holidays.filter(
                    (card) => (card.title || card.name || "").toString().trim() !== "Pending Requests"
                );
                dashboard.render(true);
            }
        } catch (e) {
            console.error("custom_timeoff: error applying immediate filter", e);
        }
    },
});

// DOM fallback: 
function removePendingRequestsCard() {
    try {
        const cards = document.querySelectorAll('.o_timeoff_card');
        cards.forEach((card) => {
            const titleEl = card.querySelector('.o_timeoff_name');
            if (titleEl && titleEl.textContent && titleEl.textContent.trim() === 'Pending Requests') {
                console.log('custom_timeoff: removing Pending Requests card from DOM');
                card.remove();
            }
        });
    } catch (e) {
        console.error('custom_timeoff: error in removePendingRequestsCard', e);
    }
}


removePendingRequestsCard();


const observer = new MutationObserver((mutations) => {
    try {
        removePendingRequestsCard();
        
        if (!document.querySelector('.custom-timeoff-header') && document.querySelector('.o_timeoff_card')) {
            insertBalancesHeader().catch(() => {});
        }
    } catch (e) {
        console.error('custom_timeoff: observer callback error', e);
    }
});

function setupObserver() {
    try {
        
        const target = (typeof document !== 'undefined') ? (document.body || document.documentElement) : null;
        if (target && typeof observer.observe === 'function') {
            observer.observe(target, { childList: true, subtree: true });
            return true;
        }
    } catch (e) {
        console.error('custom_timeoff: error setting up MutationObserver', e);
    }
    return false;
}

if (!setupObserver()) {
    
    if (typeof window !== 'undefined' && typeof window.addEventListener === 'function') {
        window.addEventListener('DOMContentLoaded', () => {
            try { setupObserver(); } catch (e) { console.error('custom_timeoff: DOMContentLoaded observer setup failed', e); }
        }, { once: true });
    }
}


// keep observer running — do not disconnect so the Pending Requests card stays removed across navigation



async function insertBalancesHeader() {
    try {
        
        const rpcPayload = {
            jsonrpc: '2.0',
            method: 'call',
            params: {
                model: 'hr.leave.allocation',
                method: 'get_logged_in_user_balances',
                args: [],
                kwargs: {},
            },
            id: new Date().getTime(),
        };
        const resp = await fetch('/web/dataset/call_kw', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(rpcPayload),
            credentials: 'same-origin',
        });
        const rpcResult = await resp.json();
        const data = rpcResult && rpcResult.result ? rpcResult.result : null;
        if (!data) {
            console.warn('custom_timeoff: no balance data returned');
            return;
        }
        let b = {
            year_2: (data.year_2 != null) ? parseFloat(data.year_2) : 0,
            year_1: (data.year_1 != null) ? parseFloat(data.year_1) : 0,
            current: (data.current != null) ? parseFloat(data.current) : 0,
            total: (data.total != null) ? parseFloat(data.total) : 0,
        };

        // Fallback: if server returned zeros
        if (b.year_2 === 0 && b.year_1 === 0 && b.current === 0 && b.total === 0) {
            try {
                
                const cards = Array.from(document.querySelectorAll('.o_timeoff_card'));
                let found = false;
                for (const card of cards) {
                    const nameEl = card.querySelector('.o_timeoff_name');
                    const durEl = card.querySelector('.o_timeoff_duration span');
                    const nameText = nameEl && nameEl.textContent && nameEl.textContent.trim();
                    const durText = durEl && durEl.textContent && durEl.textContent.trim();
                    if (nameText && /paid\s*time\s*off/i.test(nameText) && durText) {
                        const m = durText.match(/[-+]?\d*\.?\d+/);
                        if (m) {
                            const val = parseFloat(m[0]);
                            if (!isNaN(val)) {
                                b.total = val;
                                b.current = val;
                                found = true;
                                console.log('custom_timeoff: inferred total from Paid Time Off card', val);
                                break;
                            }
                        }
                    }
                }
                if (!found) {
                    // Fallback: 
                    const durationSpans = Array.from(document.querySelectorAll('.o_timeoff_card .o_timeoff_duration span'));
                    let inferredTotal = 0;
                    durationSpans.forEach((el) => {
                        const txt = el.textContent && el.textContent.trim();
                        if (txt) {
                            const m = txt.match(/[-+]?\d*\.?\d+/);
                            if (m) {
                                inferredTotal += parseFloat(m[0]);
                            }
                        }
                    });
                    if (inferredTotal > 0) {
                        b.total = inferredTotal;
                        b.current = inferredTotal;
                        console.log('custom_timeoff: inferred total from DOM', inferredTotal);
                    }
                }
            } catch (e) {
                console.error('custom_timeoff: error inferring totals from DOM', e);
            }
        }
        console.log('custom_timeoff: insertBalancesHeader', b);

        const header = document.createElement('div');
        header.className = 'o_timeoff_dashboard_header d-flex justify-content-around align-items-center custom-timeoff-header';
        const cy = new Date().getFullYear();
        header.innerHTML = `
            <div class="o_stat_box text-center">
                <div class="o_stat_value fw-bold fs-4">${b.year_2.toFixed(1)}</div>
                <div class="o_stat_label text-muted">${cy - 2} Balance</div>
            </div>
            <div class="o_stat_box text-center">
                <div class="o_stat_value fw-bold fs-4">${b.year_1.toFixed(1)}</div>
                <div class="o_stat_label text-muted">${cy - 1} Balance</div>
            </div>
            <div class="o_stat_box text-center">
                <div class="o_stat_value fw-bold fs-4">${b.current.toFixed(1)}</div>
                <div class="o_stat_label text-muted">${cy} Balance</div>
            </div>
            <div class="o_stat_box text-center">
                <div class="o_stat_value fw-bold fs-4 text-success">${b.total.toFixed(1)}</div>
                <div class="o_stat_label text-muted">Total Balance</div>
            </div>
        `;

        if (document.querySelector('.custom-timeoff-header')) {
            return;
        }

        const firstCard = document.querySelector('.o_timeoff_card');
        if (!firstCard) {
            
            return;
        }
        if (firstCard) {
           
            try {
                if (typeof firstCard.prepend === 'function') {
                    firstCard.prepend(header);
                } else {
                    firstCard.insertBefore(header, firstCard.firstChild);
                }
            } catch (e) {
                console.error('custom_timeoff: failed to prepend header into firstCard', e);
                firstCard.parentNode && firstCard.parentNode.insertBefore(header, firstCard);
            }
        } else {
            document.body.insertBefore(header, document.body.firstChild);
        }
    } catch (e) {
        console.error('custom_timeoff: insertBalancesHeader error', e);
    }
}

if (typeof window !== 'undefined') {
    if (document.readyState === 'loading') {
        window.addEventListener('DOMContentLoaded', insertBalancesHeader, { once: true });
    } else {
        insertBalancesHeader();
    }
}
