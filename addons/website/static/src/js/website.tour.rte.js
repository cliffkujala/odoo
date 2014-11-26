(function () {
    'use strict';

    var _t = openerp._t;

    openerp.Tour.register({
        id:   'website_rte',
        name: "Test website RTE",
        path: '/page/homepage?debug',
        mode: 'test',
        steps: [
            {
                element:   'button[data-action=edit]',
                title:     "Edit this page",
                wait:      250
            },
            {
                element:   'button[data-action=snippet]',
                title:     "Insert building blocks",
            },
            {
                snippet:   '#snippet_structure .oe_snippet.o_block_text_image',
                title:     "Drag & Drop a Text-Image Block",
            },
            {
                element:   '.oe_overlay_options:visible .oe_options a:first',
                title:     "Customize",
                onload: function () {
                    $(".oe_overlay_options:visible .snippet-option-background > ul").show();
                }
            },
            {
                element:   '.oe_overlay_options:visible .snippet-option-background > ul li[data-background*="quote"]:first a',
                title:     "Chose a background image",
            },
            {
                title:     "Change html for this test",
                waitFor:   '#wrapwrap > main > div > section:first[style*="background-image"]',
                element:   '#wrapwrap > main > div > section .row > div:first',
                onload: function () {
                    var $el = $(this.element);
                    var html = '<h1 id="text_title_id">Batnae municipium in Anthemusia</h1>     '+
                        '\n     <p>Batnae municipium in Anthemusia conditum Macedonum manu priscorum ab Euphrate flumine brevi spatio disparatur, refertum mercatoribus opulentis, ubi annua sollemnitate prope Septembris initium mensis ad.</p>'+
                        '\n     <p>    Quam <img class="img-responsive-25" src="/website/static/src/img/text_image.png"/> quidem <span class="fa fa-flag fa-2x"></span> partem accusationis admiratus sum et moleste tuli potissimum esse Atratino datam. Neque enim decebat neque aetas.</p>'+
                        '\n     <p>Et hanc quidem praeter oppida multa duae civitates exornant Seleucia opus Seleuci regis, et Claudiopolis quam deduxit coloniam Claudius Caesar. Isaura enim antehac nimium potens, olim subversa ut rebellatrix.</p>'+
                        '<p>Accedebant enim eius asperitati, ubi inminuta vel laesa amplitudo imperii dicebatur, et iracundae suspicionum quantitati proximorum cruentae blanditiae exaggerantium incidentia et dolere inpendio simulantium.</p>'+
                        '<p>Harum trium sententiarum nulli prorsus assentior. Nec enim illa prima vera est, ut, quem ad modum in se quisque sit, sic in amicum sit animatus. Quam multa enim, quae nostra causa numquam faceremus.</p>';
                    $el.html(html);
                    $.summernote.objects.range.create($el.find('h1')[0].firstChild, 0, $el.find('h1')[0], 0).select();
                }
            },
            {
                waitFor:   '#wrapwrap > main > div > section .row > div:first',
                element:   '.note-popover button[data-event="color"]',
                title:     "simulate triple click and change text bg-color",
                onload: function () {
                    var $el = $(this.waitFor);
                    $.summernote.objects.range.create($el.find('h1')[0].firstChild, 0, $el.find('p')[0], 0).select();
                }
            },
            {
                waitFor:   '#wrapwrap > main > div > section .row > div:first:not(:has(p font)) h1 font',
                element:   '.note-color button.dropdown-toggle',
                title:     "change selection to change text color",
            },
            {
                element:   'div[data-target-event="foreColor"] .note-color-row:eq(1) button[data-event="foreColor"]:first',
                title:     "change text color",
                onload: function () {
                    var $el = $('#wrapwrap > main > div > section .row > div:first:not(:has(p font)) h1 font');
                    $.summernote.objects.range.create($el[0].firstChild, 5, $el[0].firstChild, 10).select();
                }
            },
            {
                waitFor:   '#wrapwrap > main > div > section .row > div:first h1 font:eq(2)',
                element:   '.note-color button.dropdown-toggle',
                title:     "change selection to change text bg-color again",
            },
            {
                element:   'div[data-target-event="backColor"] .note-color-row:eq(1) button[data-event="backColor"]:eq(3)',
                title:     "change text color again",
                onload: function () {
                    var $el = $('#wrapwrap > main > div > section .row > div:first h1 font:eq(2)');
                    $.summernote.objects.range.create($el.prev()[0].firstChild, 3, $el[0].firstChild, 10).select();
                }
            },
            {
                waitFor:   '#wrapwrap > main > div > section .row > div:first h1 font:eq(4)',
                element:   '.note-color button.dropdown-toggle',
                title:     "change selection (h1 and p) to change text color with class",
            },
            {
                element:   'div[data-target-event="foreColor"] button[data-event="foreColor"][data-value^="text-"]:first',
                title:     "change text color again",
                onload: function () {
                    var $el = $('#wrapwrap > main > div > section .row > div:first h1 font:eq(4)');
                    $.summernote.objects.range.create($el.prev()[0].firstChild, 3, $el.parent("h1").next("p")[0].firstChild, 30).select();
                }
            },
            {
                waitFor:   '#wrapwrap > main > div > section .row > div:first p font',
                element:   '.o_editable.note-editable.o_dirty',
                title:     "delete selection",
                keydown:   46 // delete
            },
            {
                waitFor:   '#wrapwrap > main > div > section .row > div:first:not(:has(p font)) h1',
                element:   '.o_editable.note-editable.o_dirty',
                title:     "clean and delete an other selection",
                onload: function () {
                    var $el = $(this.waitFor);
                    $.summernote.objects.range.createFromNode($el.next("p")[0]).clean();
                    $.summernote.objects.range.create($el.find('font:last')[0].firstChild, 1, $el.next("p")[0].firstChild, 2).select();
                },
                keydown:   8 // backspace
            },
            {
                waitFor:   '#wrapwrap > main > div > section .row > div:first:has( font:last:containsExact(i) ):has( p:first:containsRegex(/^uam/) ) h1',
                element:   '.o_editable.note-editable.o_dirty',
                title:     "delete an other selection",
                onload: function () {
                    var $el = $(this.waitFor);
                    $.summernote.objects.range.create($el.find('font:first')[0].firstChild, 3, $el.next("p")[0].childNodes[2], 8).select();
                },
                keydown:   46
            },
            {
                waitFor:   '#wrapwrap > main > div > section .row > div:first:has( font:last:containsExact(Bat) )',
                title:     "gdfsgdfg",
            },
        ]
    });

}());
