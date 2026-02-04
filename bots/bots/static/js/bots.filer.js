/* Bots filer javascript functions
*
* Author: Ludovic Watteaux
*/
var ta_contents = [];

function fill_ta_content(num, numbered=true) {
    var ta_content = document.querySelector('#ta_content' + num);
    ta_content.innerText = '';
    if (numbered) {
        ta_content.classList.add('numbered');
        ta_contents[num].replaceAll('\r\n', '\n').split('\n').forEach((line) => {
            var span = document.createElement('span');
            span.innerText = line;
            ta_content.appendChild(span);
        });
    } else {
        ta_content.classList.remove('numbered');
        ta_content.innerText = ta_contents[num];
    }
}


function CreateStyle(style_id, css_content) {
    /* Create html head style element */
    var style = document.getElementById(style_id);
    if (!style) {
        style = document.createElement('style');
        style.type = 'text/css';
        style.id = style_id;
        style.innerHTML = css_content;
        document.getElementsByTagName('head')[0].appendChild(style);
    }
    return style;
}


function SetFontSize(sel) {
    /* Set font size style to .content pre */
    if (sel.selectedIndex <= 0) {
        sel.selectedIndex = 0;
        document.querySelector('.bt-less').disabled = true;
        document.querySelector('.bt-plus').disabled = false;
    } else if (sel.selectedIndex >= sel.options.length - 1) {
        sel.selectedIndex = sel.options.length - 1;
        document.querySelector('.bt-less').disabled = false;
        document.querySelector('.bt-plus').disabled = true;
    } else {
        document.querySelector('.bt-less').disabled = false;
        document.querySelector('.bt-plus').disabled = false;
    }
    var form = sel.parentElement.parentElement;
    while (!form.querySelector('.content')) {
        form = form.parentElement;
    }
    var pre = form.querySelector('.content pre');
    if (pre.classList.contains('numbered')) {
        pre.classList = 'numbered';
    } else {
        pre.classList = '';
    }
    pre.classList.add('fs' + sel.value);
}


function ScaleFont(bt) {
    /* Increase or decrease font size (-/+) */
    var sel = bt.parentElement.querySelector('#id_fontsize');
    if (bt.value === '-') {
        sel.selectedIndex -= 1;
    } else if (bt.value === '+') {
        sel.selectedIndex += 1;
    }
    SetFontSize(sel);
}
