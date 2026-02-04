/*!
* Bots ui javascript functions
*
* Author: Ludovic Watteaux
*/

function _popup(href, width='80%', height='80%', target='') {
    if (typeof(width) == 'string' && width.indexOf('%') > -1) {
        width = window.screen.width * Number(width.split('%')[0]) * 0.01;
    }
    if (typeof(height) == 'string' && height.indexOf('%') > -1) {
        height = window.screen.height * Number(height.split('%')[0]) * 0.01;
    }
    window.open(href, target||href, 'width=' + width + ', height=' + height);
}


function popup(a, width='80%', height='80%', args='') {
    if (a.href) {
        _popup(a.href + args, width, height, a.target);
    }
    return false;
}


function add_shortcut(elem) {
    var pathargs = window.location.href.split(window.location.pathname)[1]
    var shortcut_url = window.location.pathname + pathargs;
    var paths = shortcut_url.split('/');
    if (paths[paths.length - 1]) {
        var shortcut_name = paths[paths.length - 1];
        if (shortcut_name[0] == '?') {
            shortcut_name = paths[paths.length - 2] + shortcut_name;
        }
    } else {
        var shortcut_name = paths[paths.length - 2];
    }
    shortcut_name = shortcut_name.replace('?', ' ').replace('&', ' ');
    var shortcut_name = prompt('Shortcut url: ' + shortcut_url + '\nName:', shortcut_name);
    if (!shortcut_name) {
        return false;
    }
    elem.href += '?ccodeid=shortcut';
    elem.href += '&rightcode=' + encodeURIComponent(shortcut_url);
    elem.href += '&leftcode=' + encodeURIComponent(shortcut_name);
    if (elem.getAttribute('attr8')) {
        elem.href += '&attr8=' + encodeURIComponent(elem.getAttribute('attr8'));
    }
    elem.href += '&attr2=custom';
}


function saveSelection(bt) {
    /* Save selection */
    var selection_name;
    var selection = document.querySelector('#id_selection');
    var input = document.querySelector('[name="selection_name"]');
    if (input && input.value) {
        selection_name = input.value;
    } else if (selection.value) {
        selection_name = selection.value;
    } else if (!selection.querySelector('option[value="default"]')) {
        selection_name = 'default';
    } else {
        selection_name = new Date().toJSON().replaceAll(':', '').replaceAll('.', '_');
    }
    selection_name = prompt(bt.title, selection_name);
    if (!selection_name) {
        return false;
    }
    if (selection.querySelector('option[value="' + selection_name + '"]')) {
        var confirmed = confirm(gettext('Override existing selection') + ': ' + selection_name + ' ?');
        if (!confirmed) {
            return false;
        }
    }
    if (!input) {
        var div = document.createElement('div');
        div.innerHTML = '<input type="hidden" name="selection_name" value="' + selection_name + '">';
        // Avoid redirection to selectform when saving in viewform
        div.innerHTML += '<input type="hidden" name="fromselect">';
        document.querySelector("#viewform").appendChild(div);
    } else {
        input.value = selection_name;
    }
    return true;
}


function deleteSelection(bt) {
    /* Delete selection confirmation */
    var confirmed = confirm(bt.title + ' ?');
    if (!confirmed) {
        return false;
    }
    if (!document.querySelector('[name="fromselect"]')) {
        // Delete action in view, this avoid redirection to selectform
        document.forms[0].insertAdjacentHTML('beforeend', '<input type="hidden" name="fromselect">');
    }
    return true;
}
