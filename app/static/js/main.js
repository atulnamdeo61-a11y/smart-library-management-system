/**
 * Smart Library Management System - Client-side utilities
 */

document.addEventListener('DOMContentLoaded', function () {
    // 1. Initialize Bootstrap Tooltips
    var tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });

    // 2. Auto-dismiss Alert banners after 6 seconds
    var alerts = document.querySelectorAll('.alert-dismissible:not(.alert-permanent)');
    alerts.forEach(function (alertEl) {
        setTimeout(function () {
            var alertInstance = bootstrap.Alert.getOrCreateInstance(alertEl);
            if (alertInstance) {
                alertInstance.close();
            }
        }, 6000);
    });

    // 3. Confirmation dialog for sensitive actions (Delete, Reject, Waive)
    var confirmButtons = document.querySelectorAll('[data-confirm]');
    confirmButtons.forEach(function (button) {
        button.addEventListener('click', function (e) {
            var message = this.getAttribute('data-confirm') || 'Are you sure you want to proceed?';
            if (!confirm(message)) {
                e.preventDefault();
            }
        });
    });

    // 4. Quick Copy Helper
    window.copyToClipboard = function (text, btnElement) {
        navigator.clipboard.writeText(text).then(function () {
            var originalHtml = btnElement.innerHTML;
            btnElement.innerHTML = '<i class="bi bi-check2"></i> Copied!';
            setTimeout(function () {
                btnElement.innerHTML = originalHtml;
            }, 2000);
        });
    };
});
