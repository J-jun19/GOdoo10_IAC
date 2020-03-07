odoo.define('oscg_rfq.oscg_rfq', function (require) {
'use strict';
////    var session = require('web.session');
    var ListView = require('web.ListView');
//
     ListView.List.include({
        row_clicked: function() {
            var self = this;
            var context = self.dataset.get_context().eval();
//            this._super.apply(this, arguments);
            if (!context['disable_open']){
                self._super.apply(self,arguments);
            }
//                self.$buttons.find('.o_button_import').hide();
//
//            return this.$buttons;
        },
    });
});
