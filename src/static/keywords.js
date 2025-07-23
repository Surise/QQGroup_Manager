function onActionChange(select) {
    var replyInput = document.getElementById('reply-input');
    var durationInput = document.getElementById('duration-input');
    var selected = Array.from(select.selectedOptions).map(opt => opt.value);
    if (selected.includes('reply')) {
        replyInput.style.display = '';
    } else {
        replyInput.style.display = 'none';
    }
    if (selected.includes('ban')) {
        durationInput.style.display = '';
    } else {
        durationInput.style.display = 'none';
    }
}
function onRowActionChange(select, idx) {
    var row = select.closest('tr');
    var replyInput = row.querySelector('input[name="reply"]');
    var durationInput = row.querySelector('input[name="duration"]');
    var selected = Array.from(select.selectedOptions).map(opt => opt.value);
    if (selected.includes('reply')) {
        replyInput.style.display = '';
    } else {
        replyInput.style.display = 'none';
    }
    if (selected.includes('ban')) {
        durationInput.style.display = '';
    } else {
        durationInput.style.display = 'none';
    }
} 