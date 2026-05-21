// Frontend-compatible Leaflet tracking widget
// This version doesn't depend on Odoo backend modules

(function() {
    'use strict';
    
    console.log('Loading LeafletTrackingWidget...');

    // Simple frontend widget class
    function LeafletTrackingWidget(container, options) {
        console.log('LeafletTrackingWidget constructor called', container, options);
        this.container = container;
        this.shipment_id = options.shipment_id;
        this.latitude = options.latitude || 0;
        this.longitude = options.longitude || 0;
        this.zoom = options.zoom || 10;
        this.map = null;
        this.shipMarker = null;
        this.updateInterval = null;
        this.location_name = "Fetching location..."; // New field for location name
        
        this.init();
    }

    LeafletTrackingWidget.prototype.init = function() {
        var self = this;
        
        // Wait for DOM to be ready
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', function() {
                self.start();
            });
        } else {
            this.start();
        }
    };

    LeafletTrackingWidget.prototype.start = function() {
        var mapElement = this.container.querySelector("#tracking_map");
        
        if (!mapElement) {
            console.error("Map container not found");
            return;
        }
        
        // Check if Leaflet is loaded
        if (!window.L) {
            console.error("Leaflet library not loaded");
            return;
        }
        
        var lat = this.latitude || 0;
        var lon = this.longitude || 0;
        var zoom = this.zoom;
        
        // Initialize map on the correct element
        this.map = window.L.map(mapElement).setView([lat || 8.9806, lon || 38.7578], zoom);

        window.L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
            attribution: '© OpenStreetMap contributors',
            maxZoom: 18,
        }).addTo(this.map);

        // Only add marker if we have valid coordinates
        if (lat && lon && lat !== 0 && lon !== 0) {
            var shipIcon = window.L.divIcon({
                html: '<i class="fa fa-ship"></i>', // Reverted to Font Awesome
                className: 'vessel-marker tracking', // Reverted class name
                iconSize: [0, 0], // Let CSS handle the size
                iconAnchor: [20, 20] // Anchor to the center of our 40x40 CSS-defined marker
            });

            this.shipMarker = window.L.marker([lat, lon], {icon: shipIcon}).addTo(this.map)
                .bindPopup(this.shipment_id ? "Vessel" : "No Data");
        }

        // Add custom controls
        this.addCustomControls();

        // Immediately fetch the latest position on start
        this.updatePosition();

        // Start auto-updating every 30 seconds
        this.startAutoUpdate();
    };

    LeafletTrackingWidget.prototype.addCustomControls = function() {
        if (!window.L) return;
        
        var self = this;
        
        var createControl = function(options) {
            return window.L.Control.extend({
                onAdd: function() {
                    var container = window.L.DomUtil.create("div", "leaflet-bar leaflet-control leaflet-control-custom");
                    container.title = options.title;
                    container.innerHTML = '<i class="fa ' + options.icon + '"></i>';
                    window.L.DomEvent.on(container, 'click', window.L.DomEvent.stopPropagation)
                              .on(container, 'click', window.L.DomEvent.preventDefault)
                              .on(container, 'click', options.onClick);
                    return container;
                },
            });
        };

        var UpdateControl = createControl({
            title: "Update Position",
            icon: "fa-refresh",
            onClick: function() { self.updatePosition(); },
        });
        this.map.addControl(new UpdateControl({ position: "topright" }));

        var CenterControl = createControl({
            title: "Center on Ship",
            icon: "fa-crosshairs",
            onClick: function() { self.centerOnShip(); },
        });
        this.map.addControl(new CenterControl({ position: "topright" }));
    };

    LeafletTrackingWidget.prototype.updatePosition = function() {
        if (!this.shipment_id) return;

        this.showLoadingIndicator();
        
        // Simple fetch request instead of Odoo RPC
        fetch('/api/shipment_position/' + this.shipment_id, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            credentials: 'same-origin'
        })
        .then(function(response) {
            return response.json();
            
        })
        .then(async function(result) {
            if (result && result.error) {
                console.error("Position update error:", result.error);
                return;
            }

            if (result.latitude && result.longitude) {
                this.latitude = result.latitude;
                this.longitude = result.longitude;
                this.location_name = await this._fetchLocationName(result.latitude, result.longitude);
                this.addShipMarker(result.latitude, result.longitude, result);
                 
                this.map.setView([result.latitude, result.longitude]);
                this.updateLiveDataDisplay(result);
                console.log("Position updated:", result.latitude, result.longitude);
            } else {
                console.warn("No position data available");
            }
        }.bind(this)) // Correctly bind 'this' to the async function
        .catch(function(error) {
            console.error("Position update error:", error);
        })
        .finally(function() {
            this.hideLoadingIndicator();
        }.bind(this));
    };

    LeafletTrackingWidget.prototype.addShipMarker = function(lat, lon, data) {
        if (!window.L) return;
        
        if (this.shipMarker) {
            this.shipMarker.setLatLng([lat, lon]);
        } else {
            var shipIcon = window.L.divIcon({
                className: "vessel-marker", // Reverted class name
                html: '<i class="fa fa-ship"></i>', // Reverted to Font Awesome
                iconSize: [0, 0], // Let CSS handle the size
                iconAnchor: [18, 18] // Anchor to the center of our 36x36 CSS-defined marker
            });
            this.shipMarker = window.L.marker([lat, lon], { icon: shipIcon }).addTo(this.map);
        }

        var popupContent = this.createPopupContent(data || {});
        this.shipMarker.bindPopup(popupContent);
    };

    LeafletTrackingWidget.prototype.createPopupContent = function(data) {
        var vesselName = data.vessel_name || "Unknown Vessel";
        var speed = data.speed || 0;
        var course = data.course || 0;
        var status = (data.tracking_status || "not_started").replace("_", " ").toUpperCase();
        var lastUpdate = data.last_update ? new Date(data.last_update).toLocaleString() : "";
        var locationName = data.location_name || this.location_name; // Use fetched location name

        return '<div class="o_leaflet_popup">' +
            '<h6><i class="fa fa-ship"></i> ' + vesselName + '</h6>' +
            '<div class="details">' +
                '<div><strong>Location:</strong> ' + locationName + '</div>' + // New: Display location
                '<div><strong>Speed:</strong> ' + speed + ' knots</div>' +
                '<div><strong>Course:</strong> ' + course + '°</div>' +
                '<div><strong>Status:</strong> ' +
                    '<span class="tracking-status-badge ' + (data.tracking_status || "not-started") + '">' +
                        status +
                    '</span>' +
                '</div>' +
                (lastUpdate ? '<div><strong>Updated:</strong> ' + lastUpdate + '</div>' : "") +
            '</div>' +
        '</div>';
    };

    LeafletTrackingWidget.prototype.updateLiveDataDisplay = function(data) {
        var vesselEl = document.getElementById('live_vessel');
        var statusEl = document.getElementById('live_status');
        var speedEl = document.getElementById('live_speed');
        var courseEl = document.getElementById('live_course');
        var latEl = document.getElementById('live_position_lat');
        var lonEl = document.getElementById('live_position_lon');
        var updateEl = document.getElementById('live_update');
        var locationEl = document.getElementById('live_location_name'); // New: Location element

        if (vesselEl) vesselEl.textContent = data.vessel_name || 'N/A';
        if (statusEl) {
            statusEl.textContent = (data.tracking_status || 'not_started').replace('_', ' ').toUpperCase();
            statusEl.className = 'tracking-status-badge ' + (data.tracking_status || 'not-started');
        }
        if (speedEl) speedEl.textContent = (data.speed || 0).toFixed(1) + ' knots';
        if (courseEl) courseEl.textContent = (data.course || 0).toFixed(0) + '°';
        if (latEl) latEl.textContent = data.latitude.toFixed(6);
        if (lonEl) lonEl.textContent = data.longitude.toFixed(6);
        if (updateEl) updateEl.textContent = new Date().toLocaleString();
        if (locationEl) locationEl.textContent = data.location_name || this.location_name; // Update location display
    };

    LeafletTrackingWidget.prototype.centerOnShip = function() {
        if (this.shipMarker) {
            this.map.setView(this.shipMarker.getLatLng(), this.map.getZoom() < 12 ? 12 : this.map.getZoom());
            this.shipMarker.openPopup();
        }
    };

    LeafletTrackingWidget.prototype.showLoadingIndicator = function() {
        var mapElement = this.container.querySelector("#tracking_map");
        if (mapElement) {
            mapElement.classList.add("o_loading");
        }
    };

    LeafletTrackingWidget.prototype.hideLoadingIndicator = function() {
        var mapElement = this.container.querySelector("#tracking_map");
        if (mapElement) {
            mapElement.classList.remove("o_loading");
        }
    };

    LeafletTrackingWidget.prototype.startAutoUpdate = function() {
        var self = this;
        this.updateInterval = setInterval(function() {
            self.updatePosition();
        }, 30000); // 30000 ms = 30 seconds
    };

    LeafletTrackingWidget.prototype.destroy = function() {
        if (this.updateInterval) {
            clearInterval(this.updateInterval);
        }
        if (this.map) {
            this.map.remove();
        }
    };

    /**
     * Fetches a human-readable location name from coordinates using Nominatim.
     * @private
     * @param {number} lat
     * @param {number} lon
     * @returns {Promise<string>}
     */
    LeafletTrackingWidget.prototype._fetchLocationName = async function(lat, lon) {
        try {
            const response = await fetch(`https://nominatim.openstreetmap.org/reverse?format=json&lat=${lat}&lon=${lon}&zoom=18&addressdetails=1`);
            const data = await response.json();
            if (data && data.display_name) {
                // Try to get a more concise name, e.g., city, country
                const address = data.address;
                if (address.city) return `${address.city}, ${address.country}`;
                if (address.town) return `${address.town}, ${address.country}`;
                if (address.village) return `${address.village}, ${address.country}`;
                if (address.county) return `${address.county}, ${address.country}`;
                return data.display_name; // Fallback to full display name
            }
        } catch (error) {
            console.error("Error fetching location name:", error);
        }
        return "Unknown Location";
    };

    // Make it globally available
    window.LeafletTrackingWidget = LeafletTrackingWidget;
    console.log('LeafletTrackingWidget registered globally');

})();
