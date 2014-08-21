(function () {
    'use strict';

    openerp.Tour.register({
        id:   'forum_question',
        name: "try to create question",
        path: '/forum/help-1',
        mode: 'test',
        steps: [
            {
                title:     "Ask a Question",
                element:   '.btn-block a:first',
                placement: 'left',
                content:   "Ask the question in this forum by clicking on the button.",
            },
            {
                title:     "Question Title",
                element:   'input[name=post_name]',
                sampleText:'First Question Title',
                placement: 'top',
                content:   "Give your question title.",
            },
            {
                title:     "Question",
                waitNot:   'input[name=post_name]:not([value!=""])',
                element:   '.cke_editor_content',
                placement: 'top',
                content:   "Put your question here.",
                onload: function (tour) {
                    $('iframe').removeClass("cke_wysiwyg_frame");
                    $("iframe").contents().find('html').bind({
                        keydown: function(){
                            $('iframe').addClass("cke_wysiwyg_frame");
                        }
                    });
                },
                autoComplete: function (tour) {
                    if ($("iframe").contents().find("body").text() === "")
                        $("iframe").contents().find("body").text("first question");
                        $('iframe').addClass("cke_wysiwyg_frame");
                },
            },
            {
                title:     "Give Tag",
                waitFor:   'body:has(".cke_wysiwyg_frame")',
                element:   '.select2-choices',
                sampleText:'Tag',
                placement: 'top',
                content:   "Insert tags related to your question.",
            },
            {
                title:     "Post Question",
                waitNot:   'input[id=s2id_autogen2]:not([value!=Tags])',
                element:   'button:contains("Post Your Question")',
                placement: 'bottom',
                content:   "Click to post your question.",
            },
            {
                title:     "New Question Created",
                waitFor:   'body:has(".oe_grey")',
                content:   "This page contain new created question.",
                popover:   { next: "Continue" },
            },
            {
                title:     "Answer",
                element:   '.cke_browser_webkit',
                placement: 'top',
                content:   "Put your answer here.",
                onload: function (tour) {
                    $('iframe').removeClass("cke_wysiwyg_frame");
                    $("iframe").contents().find('html').bind({
                        keydown: function(){
                            $('iframe').addClass("cke_wysiwyg_frame");
                        }
                    });
                },
                autoComplete: function (tour) {
                    if ($("iframe").contents().find("body").text() === "")
                        $("iframe").contents().find("body").text("first answer");
                        $('iframe').addClass("cke_wysiwyg_frame");
                },
            },
            {
                title:     "Post Answer",
                waitFor:   'body:has(".cke_wysiwyg_frame")',
                element:   'button:contains("Post Your Reply")',
                placement: 'bottom',
                content:   "Click to post your answer.",
            },
            {
                title:     "Answer Posted",
                waitFor:   'body:has(".fa-check-circle")',
                content:   "This page contain new created question and its answer.",
                popover:   { next: "Continue" },
            },
            {
                title:     "Accept Answer",
                element:   'a[data-karma="20"]:first',
                placement: 'right',
                content:   "Click here to accept this answer.",
            },
            {
                title:     "Congratulations",
                waitFor:   'body:has(".oe_answer_true")',
                content:   "Congratulations! You just created and post your first question and answer.",
                popover:   { next: "Close Tutorial" },
            },
        ]
    });

}());
