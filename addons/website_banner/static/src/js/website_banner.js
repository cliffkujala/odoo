(function() {
    'use strict';
    var website = openerp.website,
        qweb = openerp.qweb;

    if (!website.snippet) website.snippet = {};
    website.snippet.animationRegistry.banner = website.snippet.Animation.extend({
        selector: ".bounce_banner",
        start: function (editable_mode) {
            var self = this;

            new openerp.website.banner({'el': $('#bounce_banner')});

            this.$target.find('.bouncebanner-subscribe').on('click', function (event) {
                event.preventDefault();
                console.log('1111111')
            });

            this.$target.find('.dialog-close').on('click', function(event) {
                $('body').removeClass('bouncebanner-modal-active');
                $('.bouncebanner-content').removeClass('active');
            })

            if (!editable_mode) {
                this.$target.find('.bouncebanner-subscribe').on('click', function (event) {
                    event.preventDefault();
                    self.on_click();
                });
            }
        },
        on_click: function () {
            var self = this;
            var $email = this.$target.find(".bouncebanner-email:visible");

            if ($email.length && !$email.val().match(/.+@.+/)) {
                this.$target.addClass('has-error');
                return false;
            }
            this.$target.removeClass('has-error');

            openerp.jsonRpc('/website_mass_mailing/subscribe', 'call', {
                'list_id': this.$target.data('list-id'),
                'email': $email.length ? $email.val() : false,
            }).then(function (subscribe) {
                $('body').removeClass('bouncebanner-modal-active');
                $('.bouncebanner-content').removeClass('active');
            });
        },
    });

    website.banner = openerp.Class.extend({
        init: function(options) {
            var self = this ;
            var defaults = {
                aggressive: false,
                sensitivity: 40,
                timer: 1000,
                delay: 0,
                cookie_expire: 1,
                container: $(document),
                el: ''
            };
            self.opts = $.extend({}, defaults, options);
            setTimeout(_.bind(self.do_render, self), self.opts.timer)
        },
        do_render: function() {
            var self = this;
            self.opts.container.on('mouseleave', _.bind(self.handle_mouseleave, self));
        },
        handle_mouseleave: function(e) {
            var self =  this;
            if (e.clientY > self.opts.sensitivity || (self.check_cookievalue('visited_snippet') && !self.opts.aggressive)) return;
            setTimeout(_.bind(self.show_banner,self), self.opts.delay);
        },
        set_cookie_expire: function(days) {
            var visited_snippet_list = [this.parse_cookies()['visited_snippet']]
            visited_snippet_list.push(this.opts.el.data('list-id')).toString()
            document.cookie = "visited_snippet=" + _.without(visited_snippet_list, undefined, NaN) + ";path=/"
        },
        check_cookievalue: function(cookie_name) {
            var self = this;
            var visited_snippet = self.parse_cookies()[cookie_name]
            if(visited_snippet) {
                if (self.opts.el.data('list-id') in visited_snippet.split(',') || self.opts.el.data('list-id') == visited_snippet) {
                    return true;
                }
            }
            return false;
        },
        parse_cookies: function() {
            var self = this;
            var cookies = document.cookie.split('; ');
            var res = {};
            _.each(cookies, function(cookie) {
                var el = cookie.split('=');
                res[el[0]] = el[1];
            })
            return res;
        },
        show_banner: function() {
            var self = this;
            if (self.opts.el) self.opts.el.addClass('active');
            $('body').addClass('bouncebanner-modal-active');
            self.set_cookie_expire(self.opts.cookie_expire);
        },
    });
})();

