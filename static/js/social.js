var providers_large = {
    google: {
        name: 'Google',
        url: 'https://www.google.com/accounts/o8/id'
    },
    yahoo: {
        name: 'Yahoo',
        url: 'https://me.yahoo.com/'
    },
    aol: {
        name: 'AOL',
        label: 'Enter your AOL screenname.',
        url: 'http://openid.aol.com/{username}/'
    },
    openid: {
        name: 'OpenID',
        label: 'Enter your OpenID.',
        url: null
    }
};
var providers_small = {
    myopenid: {
        name: 'MyOpenID',
        label: 'Enter your MyOpenID username.',
        url: 'http://{username}.myopenid.com/'
    },
    livejournal: {
        name: 'LiveJournal',
        label: 'Enter your Livejournal username.',
        url: 'http://{username}.livejournal.com/'
    },
    flickr: {
        name: 'Flickr',
        label: 'Enter your Flickr username.',
        url: 'http://flickr.com/photos/{username}/'
    },
    technorati: {
        name: 'Technorati',
        label: 'Enter your Technorati username.',
        url: 'http://technorati.com/people/technorati/{username}/'
    },
    wordpress: {
        name: 'Wordpress',
        label: 'Enter your Wordpress.com username.',
        url: 'http://{username}.wordpress.com/'
    },
    blogger: {
        name: 'Blogger',
        label: 'Your Blogger account',
        url: 'http://{username}.blogspot.com/'
    },
    verisign: {
        name: 'Verisign',
        label: 'Your Verisign username',
        url: 'http://{username}.pip.verisignlabs.com/'
    },
    vidoop: {
        name: 'Vidoop',
        label: 'Your Vidoop username',
        url: 'http://{username}.myvidoop.com/'
    },
    claimid: {
        name: 'ClaimID',
        label: 'Your ClaimID username',
        url: 'http://claimid.com/{username}'
    }
};
var providers = $.extend({}, providers_large, providers_small);
var openid = {
    input_id: "target_url",
    signin: function(box_id, onload) {

    	var provider = providers[box_id];
  		if (! provider) {
  			return;
  		}

        this.setOpenIdUrl(provider['url']);
        if (! onload) {
            var popup_window = window.open('','popup_window', 'width=600,height=400');
            $('#openid_form').attr("target", "popup_window");
            $('#openid_form').submit();
        }
    },
    oauth_signin: function(url, next) {
        var popup_window = window.open(url,'popup_window', 'width=600,height=400');

    },
    setOpenIdUrl: function (url) {
        $("#openid_identifier").val(url);
    }
}