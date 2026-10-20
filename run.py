# Copyright (c) 2026 Atul Namdeo (GitHub: @atulnamdeo61-a11y). All Rights Reserved.
# Proprietary and Personal Academic Project. Strictly NOT Open-Source Software.
# Unauthorized copying, distribution, or plagiarism is strictly prohibited.

import os
from app import create_app

app = create_app(os.getenv('FLASK_CONFIG', 'default'))

if __name__ == '__main__':
    # Run development server
    port = int(os.getenv('PORT', 5000))
    app.run(host='127.0.0.1', port=port, debug=True)
