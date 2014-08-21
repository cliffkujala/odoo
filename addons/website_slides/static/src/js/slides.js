(function () {
    "use strict";
    var website = openerp.website;
    var _t = openerp._t;
    website.slide = {};
    website.slide.template = website.add_template_file('/website_slides/static/src/xml/website_slides.xml');
    website.slide.Dialog = openerp.Widget.extend({
        template: 'website.slide.dialog',
        events: {
            'hidden.bs.modal': 'destroy',
            'click button.save': 'save',
            'click button[data-dismiss="modal"]': 'cancel',
            'change .slide-upload': 'slide_upload',
            'change .slide-url': 'slide_url',
            'click .list-group-item': function (ev) {
                this.$('.list-group-item').removeClass('active');
                $(ev.target).closest('li').addClass('active');
            }
        },
        init: function (el, channel_id) {
            this._super();
            this.channel_id = parseInt(channel_id, 10);
            this.file = {};
            this.index_content = "";
        },
        start: function () {
            this.$el.modal({
                backdrop: 'static'
            });
            this.set_category();
            this.set_tags();
        },
        slide_url: function (ev) {
            var self = this;
            var url = $(ev.target).val();
            this.$('.alert-warning').remove();
            this.is_valid_url = false;
            var value = {
                'url': url,
                'channel_id': self.channel_id
            };
            this.$('.save').button('loading');
            openerp.jsonRpc('/slides/dialog_preview/', 'call', value).then(function(data){
                self.$('.save').button('reset');
                if(data.error) {
                    self.display_alert(data.error);
                }else {
                    self.$("#slide-image").attr("src", data.url_src);
                    self.$('#name').val(data.title);
                    self.$('#description').val(data.description);
                    self.is_valid_url = true;
                }
            });

        },
        check_unique_slide: function (file_name) {
            var self = this;
            return openerp.jsonRpc('/web/dataset/call_kw', 'call', {
                model: 'slide.slide',
                method: 'check_unique_slide',
                args: [self.channel_id, file_name],
                kwargs: {},
            });
        },

        slide_upload: function (ev) {
            var self = this;
            var file = ev.target.files[0];
            var is_image = /^image\/.*/.test(file.type);
            this.file.name = file.name;
            this.file.type = file.type;
            if (!(is_image || this.file.type === 'application/pdf')){
                this.display_alert(_t("Invalid file type. Please select pdf or image file"));
                this.reset_file();
                return;
            }
            if (file.size/1024/1024 > 15){
                this.display_alert(_t("File is too big. Please select file upto 15MB"));
                this.reset_file();
                return;
            }
            var loaded = false;
            this.$('.alert-warning').remove();
            var BinaryReader = new FileReader();
            // file read as DataURL
            BinaryReader.readAsDataURL(file);
            BinaryReader.onloadend = function (upload) {
                var buffer = upload.target.result;
                if (is_image){
                    self.$("#slide-image").attr("src", buffer);
                }
                buffer = buffer.split(',')[1];
                self.file.data = buffer;
            };

            if (file.type === 'application/pdf') {
                var ArrayReader = new FileReader();
                this.$('.save').button('loading');
                // file read as ArrayBuffer for PDFJS get_Document API
                ArrayReader.readAsArrayBuffer(file);
                ArrayReader.onload = function (evt) {
                    var buffer = evt.target.result;
                    var passwordNeeded = function(){
                        self.display_alert(_t("You can not upload password protected file."));
                        self.reset_file();
                        self.$('.save').button('reset');
                    };
                    PDFJS.getDocument(buffer, null, passwordNeeded).then(function getPdf(pdf) {
                        pdf.getPage(1).then(function getFirstPage(page) {
                            var scale = 1;
                            var viewport = page.getViewport(scale);
                            var canvas = document.getElementById('the-canvas');
                            var context = canvas.getContext('2d');
                            canvas.height = viewport.height;
                            canvas.width = viewport.width;
                            // Render PDF page into canvas context
                            page.render({
                                canvasContext: context,
                                viewport: viewport
                            }).then(function () {
                                var image_data = self.$('#the-canvas')[0].toDataURL();
                                self.$("#slide-image").attr("src", image_data);
                                if (loaded) {
                                    self.$('.save').button('reset');
                                }
                                loaded = true;

                            });
                        });
                        var maxPages = pdf.pdfInfo.numPages;
                        self.index_content = "";
                        for (var j = 1; j <= maxPages; j++) {
                            var page = pdf.getPage(j);
                            page.then(function (page_obj) {
                                var page_number = page_obj.pageIndex + 1;
                                page_obj.getTextContent().then(function (data) {
                                    var page_content = '';
                                    _.each(data.items, function (obj) {
                                        page_content = page_content + obj.str + " ";
                                    });
                                    self.index_content = self.index_content + page_number + ". " + page_content + '\n';
                                    if (maxPages == page_number) {
                                        if (loaded) {
                                            self.$('.save').button('reset');
                                        }
                                        loaded = true;
                                    }
                                });
                            });
                        }
                    });
                };
            }

            var input = file.name;
            var input_val = input.substr(0, input.lastIndexOf('.')) || input;
            this.check_unique_slide(input_val).then(function (exist) {
                if (exist) {
                    var message = _t("Channel contains the given title, please change before Save or Publish.");
                    self.display_alert(message);
                }
                self.$('#name').val(input_val);
            });
        },
        reset_file: function(){
            var control = this.$('.slide-upload');
            control.replaceWith(control = control.clone( true ));
            this.file.name = false;
        },
        display_alert: function(message){
            this.$('.alert-warning').remove();
            $('<div class="alert alert-warning" role="alert">'+ message +'</div>').insertBefore(this.$('form'));
        },

        /**
            Wrapper for select2 load data from server at once and store it.

            @param {String} Placeholder for element.
            @param {bool}  true for multiple selection box, false for single selection
            @param {Function} Function to fetch data from remote location should return $.deferred object
            resolved data should be array of object with id and name. eg. [{'id': id, 'name': 'text'}, ...]
            @returns {Object} select2 wrapper object
        */
        select2_wrapper: function(tag, multi, fetch_fnc){
            return {
                width: '100%',
                placeholder: tag,
                formatNoMatches:_.str.sprintf(_t("No matches found. Type to create new %s"), tag),
                multiple: multi,
                selection_data: false,
                fetch_rpc_fnc : fetch_fnc,
                formatSelection: function (data) {
                    if (data.tag)
                        data.text = data.tag;
                    return data.text;
                },
                createSearchChoice: function(term) {
                    return {
                        id: _.uniqueId('tag_'),
                        create: true,
                        tag: term,
                        text: _.str.sprintf(_t("Create New %s '%s'"), tag, term)
                    };
                },
                fill_data: function(query, data){
                    var that = this,
                        tags = {results: []};
                    _.each(data, function(obj) {
                        if(that.matcher(query.term, obj.name)){
                            tags.results.push({id: obj.id, text: obj.name });
                        }
                    });
                    query.callback(tags);
                },
                query: function(query) {
                    var that = this;
                    // fetch data only once and store it
                    if (!this.selection_data){
                        this.fetch_rpc_fnc().then(function(data){
                            that.fill_data(query, data);
                            that.selection_data = data;
                        });
                    }else {
                        this.fill_data(query, this.selection_data);
                    }
                },
            };
        },

        set_category: function(){
            var self =  this;
            $('#category').select2(this.select2_wrapper(_t('Category'), false,
                function(){
                    return openerp.jsonRpc("/web/dataset/call_kw", 'call',{
                        model: 'slide.category',
                        method: 'search_read',
                        args: [],
                        kwargs: {
                            fields: ['name'],
                            domain: [['channel_id','=', self.channel_id]],
                            context: website.get_context(),
                        }
                    });
                }
            ));
        },
        set_tags: function () {
            $('#tags').select2(this.select2_wrapper(_t('Tags'), true,
                function(){
                    return openerp.jsonRpc("/web/dataset/call_kw", 'call',{
                        model: 'slide.tag',
                        method: 'search_read',
                        args: [],
                        kwargs: {
                            fields: ['name'],
                            context: website.get_context(),
                        }
                    });
                }
            ));
        },
        get_tags: function() {
            var res = [];
            // value convert to m2m create fromat
            var value = $('#tags').select2('data');
            _.each(value, function(val) {
                if (val.create)
                    res.push([0, 0, {'name': val.text}]);
                else
                    res.push([4, val.id]);
            });
            return res;
        },
        get_value: function () {
            var self = this;
            var default_val = {
                'website_published': false
            };
            var values = {};
            var canvas = this.$('#the-canvas')[0];
            if (self.file.type === 'application/pdf') {
                _.extend(values, {
                    'image': canvas.toDataURL().split(',')[1],
                    'index_content': self.index_content,
                    'slide_type': canvas.height > canvas.width ? 'document': 'presentation',
                    'mime_type': self.file.type,
                    'datas': self.file.data,
                });
            }
            if (/^image\/.*/.test(self.file.type)){
                _.extend(values, {
                    'slide_type': 'infographic',
                    'mime_type': self.file.type,
                    'datas': self.file.data
                });
            }
            _.extend(values, {
                'name': this.$('#name').val(),
                'tag_ids': this.get_tags(),
                'url': this.$('#url').val(),
                'channel_id': self.channel_id || '',
                'category_id': this.$('#category').select2('data'),
                'description': this.$('#description').val()
            });
            return _.extend(values, default_val);
        },
        validate: function () {
            this.$('.control-group').removeClass('has-error');
            if (!this.$('#name').val()) {
                this.$('#name').closest('.control-group').addClass('has-error');
                return false;
            }
            var url = this.$('#url').val()? this.is_valid_url : false;
            if (!(this.file.name || url)) {
                this.$('#url').closest('.control-group').addClass('has-error');
                return false;
            }
            return true;
        },
        save: function (ev) {
            var self = this;
            if (this.validate()) {
                var values = this.get_value();
                if ($(ev.target).data('published')) {
                    _.extend(values, {
                        'website_published': true
                    });
                }
                this.$('.slide-loading').show();
                this.$('.modal-footer, .modal-body').hide();
                openerp.jsonRpc("/slides/add_slide", 'call', values).then(function (data) {
                    if (data.error) {
                        self.display_alert(data.error);
                        self.$('.slide-loading').hide();
                        self.$('.modal-footer, .modal-body').show();

                    } else {
                        window.location = data.url;
                    }
                });
            }
        },
        cancel: function () {
            this.trigger("cancel");
        },
    });

    website.slide.PDFViewer_Launcher = function ($PDFViewer) {
        website.slide.template.then(function () {
            var slide_id = $PDFViewer.attr('slide-id'),
                file = '/slides/pdf_content/' + slide_id,
                downloadable = $PDFViewer.attr('downloadable');
            if (slide_id) {
                var PDFViewer = new website.slide.PDFViewer(slide_id, file, downloadable);
                PDFViewer.replace($PDFViewer);
                website.slide.PDFViewer_inst = PDFViewer;
            }
        });
    };

    website.slide.PDFViewer = openerp.Widget.extend({
        template: 'website.slide.PDFViewer',
        events: {
            'click #next': 'next',
            'click #previous': 'previous',
            'click #last': 'last',
            'click #first': 'first',
            'click #fullscreen': 'fullscreen',
            'change #page_number': 'change_page_number',
        },
        init: function (id, file, downloadable) {
            this.id = id;
            this.file = file;
            this.downloadable = downloadable;
            this.file_content = null;
            this.scale = 1.5;
            this.page_number = 1;
            this.rendering = false;
            this.loaded = false;
        },
        start: function () {
            this.canvas = this.$('canvas')[0];
            this.ctx = this.canvas.getContext('2d');
            this.load_file();
        },
        load_file: function () {
            var self = this;
            PDFJS.getDocument(this.file).then(function (file_content) {
                self.file_content = file_content;
                self.page_count = file_content.numPages;
                self.loaded = true;
                self.$('#PDFLoading, #PDFLoader').hide();
                self.$('#PDFViewer').show();
                self.$('#page_count').text(self.page_count);
                self.render_page();
            });
        },
        is_loaded: function(){
            if(!this.loaded){
                this.$('#PDFLoading').show();
                this.$('#PDFViewer-image').css({'opacity':0.2});
                return false;
            }
            return true;
        },
        render_page: function (page_number) {
            var self = this;
            var page_num = page_number || self.page_number;
            this.file_content.getPage(page_num).then(function (page) {
                var viewport = page.getViewport(self.scale);
                self.canvas.width = viewport.width;
                self.canvas.height = viewport.height;

                var renderContext = {
                    canvasContext: self.ctx,
                    viewport: viewport
                };
                self.rendering = true;
                page.render(renderContext).then(function () {
                    self.rendering = false;
                    self.$('#page_number').val(page_num);
                    self.page_number = page_num;
                });
            });
        },
        next: function (ev) {
            ev.preventDefault();
            if (!this.is_loaded()){
                return;
            }
            if (this.page_number === this.page_count) {
                this.fetch_next_slide();
            }
            if (this.page_number >= this.page_count) {
                return;
            }
            this.page_number += 1;
            if (!this.rendering) {
                this.render_page();
            }
        },
        fetch_next_slide: function () {
            var self = this;
            var id = parseInt(self.id, 10);
            openerp.jsonRpc('/slides/overlay/' + id, 'call')
                .then(function (data) {
                    self.$(".slide-overlay").remove();
                    $(openerp.qweb.render("website.slide.overlay", {
                        slides: data
                    })).appendTo(self.$(".slide-wrapper"));
                    self.$('.slide-thumbnail').hover(
                        function () {
                            $(this).find('.slide-caption').stop().slideDown(250); //.fadeIn(250)
                        },
                        function () {
                            $(this).find('.slide-caption').stop().slideUp(250); //.fadeOut(205)
                        }
                    );
                });
        },
        previous: function (ev) {
            ev.preventDefault();
            if (!this.is_loaded()){
                return;
            }
            if (this.page_number <= 1) {
                return;
            }
            this.$(".slide-overlay").hide();
            this.page_number -= 1;
            if (!this.rendering) {
                this.render_page();
            }
        },
        first: function (ev) {
            ev.preventDefault();
            if (!this.is_loaded()){
                return;
            }
            this.$(".slide-overlay").hide();
            this.page_number = 1;
            if (!this.rendering) {
                this.render_page();
            }
        },
        last: function (ev) {
            ev.preventDefault();
            if (!this.is_loaded()){
                return;
            }
            this.page_number = this.page_count;
            if (!this.rendering) {
                this.render_page();
            }
        },
        fullscreen: function (ev) {
            ev.preventDefault();
            //TODO: Display warning when broswer not support native fullscreen API
            website.fullScreenAPI.requestFullScreen(this.canvas);
        },
        change_page_number: function (ev) {
            var page_asked = parseInt(ev.target.value, 10);
            this.page_number = (page_asked > 0 && page_asked <= this.page_count) ? page_asked : this.page_count;
            if (!this.rendering) {
                this.render_page();
            }
        }

    });

    //Export fullscreen Browser Compatible API to website namespace
    var fullScreenApi = {
            supportsFullScreen: false,
            isFullScreen: function () {
                return false;
            },
            requestFullScreen: function () {},
            cancelFullScreen: function () {},
            fullScreenEventName: '',
            prefix: ''
        },
        browserPrefixes = 'webkit moz o ms khtml'.split(' ');

    // check for native support
    if (typeof document.cancelFullScreen != 'undefined') {
        fullScreenApi.supportsFullScreen = true;
    } else {
        // check for fullscreen support by vendor prefix
        for (var i = 0, il = browserPrefixes.length; i < il; i++) {
            fullScreenApi.prefix = browserPrefixes[i];

            if (typeof document[fullScreenApi.prefix + 'CancelFullScreen'] != 'undefined') {
                fullScreenApi.supportsFullScreen = true;
                break;
            }
        }
    }

    if (fullScreenApi.supportsFullScreen) {
        fullScreenApi.fullScreenEventName = fullScreenApi.prefix + 'fullscreenchange';

        fullScreenApi.isFullScreen = function () {
            switch (this.prefix) {
            case '':
                return document.fullScreen;
            case 'webkit':
                return document.webkitIsFullScreen;
            default:
                return document[this.prefix + 'FullScreen'];
            }
        };
        fullScreenApi.requestFullScreen = function (el) {
            return (this.prefix === '') ? el.requestFullScreen() : el[this.prefix + 'RequestFullScreen']();
        };
        fullScreenApi.cancelFullScreen = function (el) {
            return (this.prefix === '') ? document.cancelFullScreen() : document[this.prefix + 'CancelFullScreen']();
        };
    }

    website.fullScreenAPI = fullScreenApi;

})();

$(document).ready(function () {
    var website = openerp.website;
    var _t = openerp._t;

    website.slide.PDFViewer_Launcher($('#PDFViewer'));
    $("timeago.timeago").each(function(index, el){
        var datetime = $(el).attr('datetime');
        var datetime_obj = openerp.str_to_datetime(datetime);
        // if presentation 7 days, 24 hours, 60 min, 60 second, 1000 millis old(one week)
        // then return fix formate string else timeago
        var display_str = "";
        if (datetime_obj && new Date().getTime()- datetime_obj.getTime() > 7*24*60*60*1000) {
            display_str = datetime_obj.toDateString();
        }else{
            display_str= $.timeago(datetime_obj);
        }
        $(el).text(display_str);
    });

    $('.slide-container').on('click', function (ev) {
        window.location = $(this).find("a").attr("href");
    });
    $('.slide-tabs').on('click', function (ev) {
        ev.preventDefault();
        window.location = $(this).attr('href');
    });

    $('.slide-like, .slide-unlike').on('click', function (ev) {
        ev.preventDefault();
        var slide_id = $(this).attr('slide-id');
        var user_id = $(this).attr('user-id');
        var $link = $(ev.currentTarget);
        if (localStorage['slide_vote_' + slide_id] != user_id) {
            openerp.jsonRpc($link.data('href'), 'call', {}).then(function (data) {
                $($link.data('count-el')).text(data);
            });
            localStorage['slide_vote_' + slide_id] = user_id;
        } else {
            var $warning = $('<div class="alert alert-danger alert-dismissable oe_forum_alert" id="vote_alert">' +
                '<button type="button" class="close notification_close" data-dismiss="alert" aria-hidden="true">&times;</button>' +
                _t('You have already voted for this slide') +
                '</div>');
            if (!$link.parent().find('#vote_alert').length) {
                $link.parent().append($warning);
            }
        }
    });
    $('.upload').on('click', function (ev) {
        var channel_id = $(this).attr('channel_id');
        new website.slide.Dialog(this, channel_id).appendTo(document.body);
    });

    $(document).keydown(function (ev) {
        if (ev.keyCode == 37) {
            website.slide.PDFViewer_inst.previous(ev);
        }
        if (ev.keyCode == 39) {
            website.slide.PDFViewer_inst.next(ev);
        }
    });

    website.slide.modifyembedcode = function (currentVal) {
        var $embed_input = $('.slide_embed_code');
        var slide_embed_code = $embed_input.val();
        var tmp_embed_code = slide_embed_code.replace(/(page=).*?([^\d]+)/, '$1' + currentVal + '$2');
        $embed_input.val(tmp_embed_code);
    };

    $('.embed-page-counter').on('change', function (e) {
        e.preventDefault();
        var currentVal = parseInt($(this).val());
        var maxval = parseInt($('#page_count').text());
        if (currentVal > 0 && currentVal <= maxval) {
            website.slide.modifyembedcode(currentVal);
        } else {
            $(this).val(1);
            website.slide.modifyembedcode(1);
        }
    });
    $('.share-toggle-option').on('click', function (ev) {
        ev.preventDefault();
        var toggleDiv = $(this).data('slide-share');
        $(toggleDiv).slideToggle();
    });


    if ($('div#statistic').length) {
        var socialgatter = function (app_url, url, callback) {
            $.ajax({
                url: app_url + url,
                dataType: 'jsonp',
                success: callback
            });
        };
        var current_url = window.location.origin + window.location.pathname;
        socialgatter('http://www.linkedin.com/countserv/count/share?url=', current_url, function (data) {
            $('#linkedin-badge').text(data.count || 0);
            $('#total-share').text(parseInt($('#total-share').text()) + parseInt($('#linkedin-badge').text()));
        });
        socialgatter('http://cdn.api.twitter.com/1/urls/count.json?url=', current_url, function (data) {
            $('#twitter-badge').text(data.count || 0);
            $('#total-share').text(parseInt($('#total-share').text()) + parseInt($('#twitter-badge').text()));
        });
        socialgatter('http://graph.facebook.com/?id=', current_url, function (data) {
            $('#facebook-badge').text(data.shares || 0);
            $('#total-share').text(parseInt($('#total-share').text()) + parseInt($('#facebook-badge').text()));
        });

        $.ajax({
            url: 'https://clients6.google.com/rpc',
            type: "POST",
            dataType: 'json',
            contentType: 'application/json',
            data: JSON.stringify([{
                "method": "pos.plusones.get",
                "id": "p",
                "params": {
                    "nolog": true,
                    "id": current_url,
                    "source": "widget",
                    "userId": "@viewer",
                    "groupId": "@self"
                },
                "jsonrpc": "2.0",
                "key": "AIzaSyCFi7q20yMDmAZ9Qxmiu-zHPnxvIX0u2zM",
                "apiVersion": "v1"
            }]),
            success: function (data) {
                $('#google-badge').text(data[0].result.metadata.globalCounts.count || 0);
                $('#total-share').text(parseInt($('#total-share').text()) + parseInt($('#google-badge').text()));
            }
        });
    }

    $('.send-share-email').on('click', function () {
        var $input = $(this).parent().prev(':input');
        if (!$input.val() || !$input[0].checkValidity()) {
            $input.closest('.form-group').addClass('has-error');
            $input.focus();
            return;
        }
        $input.closest('.form-group').removeClass('has-error');
        $(this).button('loading');
        openerp.jsonRpc('/slides/send_share_email/' + $(this).attr('slide-id'), 'call', {
            email: $input.val()
        }).then(function () {
            $input.closest('.form-group').html($('<div class="alert alert-info" role="alert"><strong>Thank you!</strong> Mail has been sent.</div>'));
        });
    });

});
