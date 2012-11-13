var module = angular.module('wbMessages', []);

module.constant('ASAP', "מיידי");
module.constant('DefaultMessages', {
        today: "היום",
        or_less: "או פחות",
        pickup: "איסוף",
        pickup_address: "כתובת מוצא",
        dropoff_address: "כתובת יעד",
        available_seats: "מושבים פנויים",
        you: "את/ה",
        private_ride: "נסיעה פרטית",
        connection_error:'לא ניתן להשלים את הפעולה עקב שגיאה או בעיית חיבור לרשת',
        billing_error:'לא ניתן לבצע חיוב בכרטיס זה. ייתכן והכרטיס עימו נרשמת פג תוקף, חסום או שאינו נתמך במערכת (אמריקן אקספרס).',
        loading_offers_1: "מאתר נסיעות חופפות",
        loading_offers_2: "מחשב זמני נסיעה",
        loading_offers_3: "מעדכן מוניות",
        loading_book_ride: "מבצע הזמנה",
        loading_billing: "מאמת אמצעי תשלום",
        loading_private_offer: "מחשב מחיר נסיעה פרטית",
        loading_update_picture: "מפנה אל Facebook",
        no_offers: "לא נמצאו נסיעות מתאימות",

        missing_house_number: "השלם מספר בית",
        unknown_address: "כתובת לא ידועה",

        book_existing_ride_txt: 'הצטרף לנסיעה',
        book_new_ride_txt: 'הזמן נסיעה',
        confirm_cancel_order: "האם לבטל את הנסיעה?",
        cancel_ride: 'בטל נסיעה',
        report_ride: 'דווח על בעיה'
    }
);