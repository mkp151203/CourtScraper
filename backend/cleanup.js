// Temporary Downloads Cleanup for Court Scraper
// Add this script to your frontend to automatically clean up downloads on page refresh

(function() {
    // Function to call cleanup endpoint
    function cleanupDownloads() {
        try {
            // Use sendBeacon for reliability during page unload
            const url = '/api/cleanup-downloads';
            const data = JSON.stringify({});
            
            if (navigator.sendBeacon) {
                navigator.sendBeacon(url, data);
            } else {
                // Fallback for older browsers
                fetch(url, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: data,
                    keepalive: true
                }).catch(() => {
                    // Ignore errors during cleanup
                });
            }
        } catch (error) {
            // Ignore cleanup errors
            console.log('Cleanup failed:', error);
        }
    }

    // Clean up on page unload (refresh, close, navigate away)
    window.addEventListener('beforeunload', cleanupDownloads);
    window.addEventListener('unload', cleanupDownloads);
    
    // Also clean up when visibility changes (tab switching, etc.)
    document.addEventListener('visibilitychange', function() {
        if (document.visibilityState === 'hidden') {
            cleanupDownloads();
        }
    });

    console.log('Temporary downloads cleanup initialized');
})();