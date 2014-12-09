(function () {
    'use strict';

    var _t = openerp._t;
    var website = openerp.website;
    var qweb = openerp.qweb;
    website.add_template_file('/website_forum/static/src/xml/website_forum.share_templates.xml');

    website.ready().done(function() {
        if ($('.question').data('type')=="question") {
        var diff_date = Date.now()-Date.parse($('.question').data('last-update').split(' ')[0]);
        }
        var is_answered = !!$('.forum_answer').length;
        //If the question is older than 864*10e5 seconds (=10 days) and does'nt have an answer
        if (diff_date && diff_date > 864*10e5 && !is_answered) {
            var hashtag_list = ['question'];
            var social_list = ['facebook','twitter', 'linkedin', 'google-plus'];
            new website.social_share('social_alert',$(this), social_list, hashtag_list);
            $('.share').on('click', $.proxy(updateDateWrite));
        }
        function updateDateWrite() {
            openerp.jsonRpc(window.location.pathname+'/bump', 'call', {});
        };
    });})();
