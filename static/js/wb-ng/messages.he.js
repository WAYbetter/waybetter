var module = angular.module('wbMessages', []);

module.constant('ASAP', "מיידי");
module.constant('DefaultMessages', {
        today: "היום",
        connection_error:'לא ניתן להשלים את הפעולה עקב שגיאה או בעיית חיבור לרשת',
        loading_offers_1: "מאתר נסיעות חופפות",
        loading_offers_2: "מחשב זמני נסיעה",
        loading_offers_3: "מעדכן מוניות",
        loading_book_ride: "מבצע הזמנה",
        loading_private_offer: "מחשב מחיר נסיעה פרטית",
        confirm_cancel_order: "",
        no_offers: "לא נמצאו נסיעות מתאימות",

        book_existing_ride_txt: 'הצטרף לנסיעה',
        book_new_ride_txt: 'התחל נסיעה חדשה'
    }
);