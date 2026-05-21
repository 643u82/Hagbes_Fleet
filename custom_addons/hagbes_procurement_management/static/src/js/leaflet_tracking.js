odoo.define("foreign_procurement.leaflet_tracking", function (require) {
    "use strict";

    var core = require("web.core");
    var Widget = require("web.Widget");
    var rpc = require("web.rpc");

    const { _t } = core;

    const LeafletTrackingWidget = Widget.extend({
        template: "foreign_procurement.leaflet_tracking_widget",

        init: function (parent, options) {
            this._super.apply(this, arguments);
            this.shipment_id = options.shipment_id;
            this.latitude = options.latitude || 0;
            this.longitude = options.longitude || 0;
            this.zoom = options.zoom || 10;
            this.map = null;
            this.shipMarker = null;
            this.updateInterval = null;
        },

        start: function () {
            var self = this;
            var mapElement = this.el.querySelector("#tracking_map");
            
            if (!mapElement) {
                console.error("Map container not found");
                return this._super();
            }
            
            // Check if Leaflet is loaded
            if (!window.L) {
                console.error("Leaflet library not loaded");
                return this._super();
            }
            
            var lat = this.latitude || 0;
            var lon = this.longitude || 0;
            var zoom = this.zoom;
            
            // Initialize map on the correct element
            this.map = window.L.map(mapElement).setView([lat || 8.9806, lon || 38.7578], zoom); // Default to Addis Ababa if no coordinates

            window.L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
                attribution: '© OpenStreetMap contributors',
                maxZoom: 18,
            }).addTo(this.map);

            // Only add marker if we have valid coordinates
            if (lat && lon && lat !== 0 && lon !== 0) {
                var shipIcon = window.L.divIcon({
                    html: '<i class="fa fa-ship"></i>', // Ensure Font Awesome icon
                    className: 'vessel-marker tracking',
                    iconSize: [40, 40],
                    iconAnchor: [20, 20]
                });

                this.shipMarker = window.L.marker([lat, lon], {icon: shipIcon}).addTo(this.map)
                    .bindPopup(this.shipment_id ? "Vessel" : "No Data");
            }

            // Optionally start auto-update
            // this._startAutoUpdate();
            
            return this._super();
        },

        destroy: function () {
            if (this.updateInterval) {
                clearInterval(this.updateInterval);
            }
            if (this.map) {
                this.map.remove();
            }
            this._super();
        },

        //--------------------------------------------------------------------------
        // Private
        //--------------------------------------------------------------------------

        /**
         * Initializes the Leaflet map, tiles, and controls.
         * @private
         */
        _initializeMap: function () {
            if (!window.L) return;
            
            const mapElement = this.el.querySelector("#tracking_map");
            if (!mapElement) return;

            this.map = window.L.map(mapElement).setView([this.latitude, this.longitude], this.zoom);

            window.L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
                attribution: '© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
                maxZoom: 18,
            }).addTo(this.map);

            if (this.latitude && this.longitude) {
                this._addShipMarker(this.latitude, this.longitude);
            }

            this._addCustomControls();
        },

        /**
         * Adds or updates the ship marker on the map.
         * @private
         * @param {number} lat
         * @param {number} lon
         * @param {Object} [data={}] - Data for the popup.
         */
        _addShipMarker: function (lat, lon, data = {}) {
            if (!window.L) return;
            
            if (this.shipMarker) {
                this.shipMarker.setLatLng([lat, lon]);
            } else {
                const shipIcon = window.L.divIcon({
                    className: "vessel-marker", 
                    html: '<i class="fa fa-ship"></i>',
                    iconSize: [36, 36],
                    iconAnchor: [18, 18],
                });
                this.shipMarker = window.L.marker([lat, lon], { icon: shipIcon }).addTo(this.map);
            }

            const popupContent = this._createPopupContent(data);
            this.shipMarker.bindPopup(popupContent);
        },

        /**
         * Creates the HTML content for the marker's popup.
         * @private
         * @param {Object} data
         * @returns {string}
         */
        _createPopupContent: function (data) {
            const vesselName = _.escape(data.vessel_name || _t("Unknown Vessel"));
            const speed = _.escape(data.speed || 0);
            const course = _.escape(data.course || 0);
            const status = _.escape((data.tracking_status || "not_started").replace("_", " ").toUpperCase());
            const lastUpdate = data.last_update ? new Date(data.last_update).toLocaleString() : "";

            return `
                <div class="o_leaflet_popup">
                    <h6><i class="fa fa-ship"></i> ${vesselName}</h6>
                    <div class="details">
                        <div><strong>${_t("Speed")}:</strong> ${speed} knots</div>
                        <div><strong>${_t("Course")}:</strong> ${course}°</div>
                        <div><strong>${_t("Status")}:</strong> 
                            <span class="tracking-status-badge ${data.tracking_status || "not-started"}">
                                ${status}
                            </span>
                        </div>
                        ${lastUpdate ? `<div><strong>${_t("Updated")}:</strong> ${lastUpdate}</div>` : ""}
                    </div>
                </div>
            `;
        },

        /**
         * Adds custom controls (Update, Center) to the map.
         * @private
         */
        _addCustomControls: function () {
            if (!window.L) return;
            
            const createControl = (options) => {
                return window.L.Control.extend({
                    onAdd: () => {
                        const container = window.L.DomUtil.create("div", "leaflet-bar leaflet-control leaflet-control-custom");
                        container.title = options.title;
                        container.innerHTML = `<i class="fa ${options.icon}"></i>`;
                        window.L.DomEvent.on(container, 'click', window.L.DomEvent.stopPropagation)
                                  .on(container, 'click', window.L.DomEvent.preventDefault)
                                  .on(container, 'click', options.onClick);
                        return container;
                    },
                });
            };

            const UpdateControl = createControl({
                title: _t("Update Position"),
                icon: "fa-refresh",
                onClick: () => this._updatePosition(),
            });
            this.map.addControl(new UpdateControl({ position: "topright" }));

            const CenterControl = createControl({
                title: _t("Center on Ship"),
                icon: "fa-crosshairs",
                onClick: () => this._centerOnShip(),
            });
            this.map.addControl(new CenterControl({ position: "topright" }));
        },

        /**
         * Fetches the latest position from the server and updates the map.
         * @private
         */
        _updatePosition: async function () {
            if (!this.shipment_id) return;

            this._showLoadingIndicator();
            try {
                const result = await rpc.query({
                    route: `/api/shipment_position/${this.shipment_id}`,
                    params: {}
                });

                if (result.error) {
                    console.error("Position update error:", result.error);
                    return;
                }

                if (result.latitude && result.longitude) {
                    this.latitude = result.latitude;
                    this.longitude = result.longitude;
                    this._addShipMarker(result.latitude, result.longitude, result);
                    this.map.setView([result.latitude, result.longitude]);
                    this._updateLiveDataDisplay(result);
                    console.log("Position updated:", result.latitude, result.longitude);
                } else {
                    console.warn("No position data available");
                }
            } catch (error) {
                console.error("Position update error:", error);
            } finally {
                this._hideLoadingIndicator();
            }
        },

        /**
         * Updates the live data display panel on the page.
         * @private
         */
        _updateLiveDataDisplay: function (data) {
            $('#live_vessel').text(data.vessel_name || 'N/A');
            const statusBadge = $('#live_status');
            statusBadge.text((data.tracking_status || 'not_started').replace('_', ' ').toUpperCase());
            statusBadge.attr('class', 'tracking-status-badge ' + (data.tracking_status || 'not-started'));

            $('#live_speed').text((data.speed || 0).toFixed(1) + ' knots');
            $('#live_course').text((data.course || 0).toFixed(0) + '°');
            $('#live_position_lat').text(data.latitude.toFixed(6));
            $('#live_position_lon').text(data.longitude.toFixed(6));
            $('#live_update').text(new Date().toLocaleString());
        },

        /**
         * Centers the map view on the ship marker.
         * @private
         */
        _centerOnShip: function () {
            if (this.shipMarker) {
                this.map.setView(this.shipMarker.getLatLng(), this.map.getZoom() < 12 ? 12 : this.map.getZoom());
                this.shipMarker.openPopup();
            }
        },

        /**
         * Starts the automatic update interval.
         * @private
         */
        _startAutoUpdate: function () {
            this.updateInterval = setInterval(() => {
                this._updatePosition();
            }, 60000); // 60 seconds
        },

        /**
         * Shows a loading overlay on the map.
         * @private
         */
        _showLoadingIndicator: function () {
            var mapElement = this.el.querySelector("#tracking_map");
            if (mapElement) {
                mapElement.classList.add("o_loading");
            }
        },

        /**
         * Hides the loading overlay.
         * @private
         */
        _hideLoadingIndicator: function () {
            var mapElement = this.el.querySelector("#tracking_map");
            if (mapElement) {
                mapElement.classList.remove("o_loading");
            }
        },
    });

    return LeafletTrackingWidget;
});
