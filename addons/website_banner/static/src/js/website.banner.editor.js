(function () {
    'use strict';
    var website = openerp.website;
    var _t = openerp._t;

    website.snippet.options.bounce_banner = website.snippet.Option.extend({
        choose_mailing_list: function (type, value) {
            var self = this;
            if (type !== "click") return;
            return website.prompt({
                id: "editor_new_mailing_list_subscribe_Banner",
                window_title: _t("Add a Newsletter Subscribe Banner"),
                select: _t("Newsletter"),
                init: function (field) {
                    return website.session.model('mail.mass_mailing.list')
                            .call('name_search', ['', []], { context: website.get_context() });
                },
            }).then(function (mailing_list_id) {
                self.$target.attr("data-list-id", mailing_list_id);
            });
        },
        drop_and_build_snippet: function() {
            var self = this;
            this._super();
            this.choose_mailing_list('click').fail(function () {
                self.editor.on_remove();
            });
        },
        clean_for_save: function () {
            //this.$target.addClass('hidden')
        },
    });
    
    website.EditorBar.include({
            edit: function () {
                var self = this;
                $('.popover').remove();
                this._super();
                var vHeight = $(window).height();
                $('body').on('click','#edit_dialog',_.bind(this.edit_dialog, self.rte.editor, vHeight));
                $('body').on('click','.dialog-close',_.bind(this.close_dialog, self.rte.editor));
            },
            save : function() {
                var res = this._super();
                console.log('11111111111',$('.bouncebanner-content.active'))
                //debugger
                $('.bouncebanner-content.active').removeClass('active');
                return res;
            },
            edit_dialog : function(vHeight) {
                var self  = this;

                var $target = $($('#edit_dialog').data('target'));
                var $button = $('#edit_dialog')

                $target.css({
                    top:          $button.offset().top - $(window).scrollTop(),
                    left:         $button.offset().left - $(window).scrollLeft(),
                    width:        $button.css('width'),
                    maxHeight:    $button.css('height'),
                    opacity:      1,
                    transition:   'none'
                });

                $('body').addClass('morphbutton-modal-active');
                $('.bouncebanner-content').addClass('active');

            },
            close_dialog: function() {
                var self  = this;

                var $target = $($('#edit_dialog').data('target'));
                var $button = $('#edit_dialog')
                $('body').removeClass('morphbutton-modal-active');
                $('.bouncebanner-content').removeClass('active');
            },
        });
})();
