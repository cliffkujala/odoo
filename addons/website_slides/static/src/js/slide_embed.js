$(document).ready(function() {

if($('#pdfcanvas').get(0)){
    PDFJS.disableWorker = true;

    var pdfDoc = null,
        pageNum = 1,
        pageRendering = false,
        pageNumPending = null,
        scale = 1.5,
        url = $('#pdf_file').val(),
        canvas = $('#pdfcanvas').get(0),
        ctx = canvas.getContext('2d');

    /**
     * Get page info from document, resize canvas accordingly, and render page.
     * @param num Page number.
     */
    function renderPage(num) {
        pageRendering = true;
        // Using promise to fetch the page
        pdfDoc.getPage(num).then(function(page) {
            var viewport = page.getViewport(scale);
            canvas.height = viewport.height;
            canvas.width = viewport.width;
            // Render PDF page into canvas context
            var renderContext = {
                canvasContext: ctx,
                viewport: viewport
            };
            var renderTask = page.render(renderContext);
            // Wait for rendering to finish
            renderTask.promise.then(function () {
                pageRendering = false;
                if (pageNumPending !== null) {
                    // New page rendering is pending
                    renderPage(pageNumPending);
                    pageNumPending = null;
                }
            });
        });
        // Update page counters
        $('#page_number').val(pageNum);
        //Hide all slide option on page render
        $('.slide-option-toggle').hide();
    }

    /**
     * If another page rendering in progress, waits until the rendering is
     * finised. Otherwise, executes rendering immediately.
     */
    function queueRenderPage(num) {
        if (pageRendering) {
            pageNumPending = num;
        } else {
            renderPage(num);
        }
    }

    /**
     * Displays previous page.
     */
    function onPrevPage() {
        if (pageNum <= 1) {
            return;
        }
        pageNum--;
        queueRenderPage(pageNum);
    }
    $('#previous').on('click', function(e){ onPrevPage() });

    /**
     * Displays next page.
     */
    function onNextPage() {
        if (pageNum === pdfDoc.numPages) {
            $('.slide-option-toggle').hide();
            $("#slide_suggest").slideToggle();
        }
        if (pageNum >= pdfDoc.numPages) {
            return;
        }
        pageNum++;
        queueRenderPage(pageNum);
    }
    $('#next').on('click', function(e){ onNextPage() });

    /**
     * Displays last page.
     */
    function onLastPage() {  
        pageNum = pdfDoc.numPages;
        queueRenderPage(pdfDoc.numPages);
    }
    $('#last').on('click', function(e){ onLastPage() });

    /**
     * Displays first page.
     */
    function onFirstPage() {  
        pageNum = 1;
        queueRenderPage(1);
    }
    $('#first').on('click', function(e){ onFirstPage() });

    /**
     * Displays Search page.
     */
    function onPagecSearch() {
        var currentVal = parseInt($('#page_number').val());
        if(currentVal > 0 && currentVal <= pdfDoc.numPages){
            pageNum = currentVal;
            renderPage(pageNum);
        }else{
            $('#page_number').val(pageNum);
        }
    }
    $('#page_number').on('change', function(e){ onPagecSearch() });

    /**
     * Asynchronously downloads PDF.
     */
    PDFJS.getDocument(url).then(function (pdfDoc_) {
        pdfDoc = pdfDoc_;
        $('#page_count').text(pdfDoc.numPages);
        var initpage = parseInt($('#pdf_page').val());
        pageNum = (initpage > 0 && initpage <= pdfDoc.numPages)? initpage : 1;
        // Initial/first page rendering
        renderPage(pageNum);
        $('#slide_init_image').hide();
        $('#pdfcanvas').show();
    });

    /**
     * For full screen mode 
     */
    function toggleFullScreen() {
        var elem = $("#pdfcanvas").get(0);
        if (!elem.fullscreenElement && !elem.mozFullScreenElement && !elem.webkitFullscreenElement && !elem.msFullscreenElement ) {
            if (elem.requestFullscreen) {
                elem.requestFullscreen();
            } else if (elem.msRequestFullscreen) {
                elem.msRequestFullscreen();
            } else if (elem.mozRequestFullScreen) {
                elem.mozRequestFullScreen();
            } else if (elem.webkitRequestFullscreen) {
                elem.webkitRequestFullscreen(Element.ALLOW_KEYBOARD_INPUT);
            }
        } else {
            if (elem.exitFullscreen) {
                elem.exitFullscreen();
            } else if (elem.msExitFullscreen) {
                elem.msExitFullscreen();
            } else if (elem.mozCancelFullScreen) {
                elem.mozCancelFullScreen();
            } else if (elem.webkitExitFullscreen) {
                elem.webkitExitFullscreen();
            }
        }
    }
    $('#fullscreen').on('click', function(e){ toggleFullScreen() });

    $(document).keydown(function(ev){
        if (ev.keyCode == 37) {
            onPrevPage();
        }
        if (ev.keyCode == 39) {
            onNextPage();
        }
    });
} //end pdf condition

    $('.slide-like, .slide-unlike').on('click', function(ev){
        ev.preventDefault();
        var slide_id = $(this).attr('slide-id');
        var user_id = $(this).attr('user-id');
        if(localStorage['slide_vote_' + slide_id] != user_id){
            var $link = $(ev.currentTarget);
            $.ajax({
                type: "POST",
                dataType: 'json',
                url: $link.data('href'),
                async: false,
                contentType: "application/json; charset=utf-8",
                data: JSON.stringify({}),
                success: function (data) {
                    $($link.data('count-el')).text(data.result);
                }
            });
            localStorage['slide_vote_' + slide_id] = user_id;
        }
    });

    function modifyembedcode(currentVal) {
        var $embed_input = $('.slide_embed_code');
        var slide_embed_code = $embed_input.val();
        var tmp_embed_code = slide_embed_code.replace(/(page=).*?([^\d]+)/,'$1' + currentVal + '$2');
        $embed_input.val(tmp_embed_code);
    };

    $('.embed-page-counter').on('change', function(e){
        e.preventDefault();
        var currentVal = parseInt($(this).val());
        var maxval = parseInt($('#page_count').text());
        if(currentVal > 0 && currentVal <= maxval){
            modifyembedcode(currentVal);
        }else{
            $(this).val(1);
            modifyembedcode(1);
        }
    });

    $('.toggle-slide-option').on('click', function (ev) {
        ev.preventDefault();
        var toggleDiv = $(this).data('slide-option-id');
        $('.slide-option-toggle').not(toggleDiv).each(function() {
            $(this).hide();
        });
        $(toggleDiv).slideToggle();
    });

    $('.slide_suggest_detail').on('hover', function (ev) {
        var toggleDiv = $(this).data('slide-suggest-detail-id');
        $(toggleDiv).slideToggle();
    });
    $.post( "/slides/embed/count", {
        slide: parseInt($('#pdf_id').val()),
        url: document.referrer
    });

    $('.send-share-email').on('click', function (ev) {
        var $input = $(this).parent().prev(':input');
        if (!$input.val() || !$input[0].checkValidity()) {
            $input.closest('.form-group').addClass('has-error');
            $input.focus();
            return;
        }
        $input.closest('.form-group').removeClass('has-error');
        $.ajax({
            type: "POST",
            dataType: 'json',
            url: '/slides/send_share_email/' + $(this).attr('slide-id'),
            async: false,
            contentType: "application/json; charset=utf-8",
            data: JSON.stringify({email: $input.val()}),
            success: function (data) {
                $input.closest('.form-group').html($('<div class="alert alert-info" role="alert"><strong>Thank you!</strong> Mail has been sent.</div>'));
            }
        });
    });

});