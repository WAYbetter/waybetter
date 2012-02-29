document.write('<script src="{{ map_provider_url }}">\x3C/script>');
function updateTelmapSettings() {
    if (!window.mapController) {
        setTimeout(updateTelmapSettings, 1);
    } else {

        mapController.didLogin = function (response, status) {

            this._log('didLogin', {response:response, status:status});
        };
        var prefs = {
            contextUrl:"api.telmap.com/telmapnav",
            userName:"{{ map_username }}",
            password:"{{ map_password }}"
        };

        mapController.init(prefs);
    }
}

setTimeout(updateTelmapSettings, 1);
