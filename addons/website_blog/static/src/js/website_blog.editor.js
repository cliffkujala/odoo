(function() {
    "use strict";

    var website = openerp.website;
    var _t = openerp._t;

    website.EditorBarContent.include({
        new_blog_post: function() {
            website.prompt({
                id: "editor_new_blog",
                window_title: _t("New Blog Post"),
                select: "Select Blog",
                init: function (field) {
                    return website.session.model('blog.blog')
                            .call('name_search', [], { context: website.get_context() });
                },
            }).then(function (cat_id) {
                document.location = '/blogpost/new?blog_id=' + cat_id;
            });
        },
    });
    if ($('.website_blog').length) {
        website.EditorBar.include({
            edit: function () {
                var self = this;
                $('.popover').remove();
                this._super();
                var vHeight = $(window).height();
            },
            save : function() {
                var res = this._super();
                var $cover = $('#title.cover');
                if ($cover.length) {
                    var src = $cover.css("background-image").replace(/url\(|\)|"|'/g,'').replace(/.*none$/,'');
                    openerp.jsonRpc("/blogpost/change_background", 'call', {
                        'post_id' : +$('[data-oe-model="blog.post"]').attr('data-oe-id'),
                        'image' : src,
                    });
                }
                return res;
            },
        });
        
        website.snippet.options.many2one.include({
            select_record: function (li) {
                this._super(li);
                if (this.$target.is('.blog_title div [data-oe-field="author_id"]')) {
                    this.$target.prev('[data-oe-field="author_avatar"]').find("img").attr("src", "/website/image/res.partner/"+this.ID+"/image");
                }
            }
        });
    }

    website.snippet.options.website_blog = website.snippet.Option.extend({
        start : function(type, value, $li) {
            this._super();
            this.src = this.$target.css("background-image").replace(/url\(|\)|"|'/g,'').replace(/.*none$/,'');
            this.$image = $('<image src="'+this.src+'">');
        },
        clear : function(type, value, $li) {
            if (type !== 'click') return;
            this.src = null;
            this.$target.css({"background-image": '', 'min-height': $(window).height()});
            this.$image.removeAttr("src");
        },
        change : function(type, value, $li) {
            if (type !== 'click') return;
            var self = this;
            var editor  = new website.editor.MediaDialog(this.$image, this.$image[0]);
            editor.appendTo('body');
            editor.on('saved', self, function (event, img) {
                var url = self.$image.attr('src');
                self.$target.css({"background-image": url ? 'url(' + url + ')' : "", 'min-height': $(window).height()});
            });
        },
    });

})();
