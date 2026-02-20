/**
 * ARIA WhatsApp Bridge - Node.js Server
 * =====================================
 * A simple HTTP server that provides WhatsApp automation for ARIA agent.
 * Uses whatsapp-web.js for browser-based WhatsApp Web automation.
 * 
 * Usage:
 *   npm install
 *   node index.js
 * 
 * API Endpoints:
 *   POST /send      - Send message { to: "phone", message: "text" }
 *   POST /search    - Search for chat { query: "name" }
 *   GET  /chats     - List recent chats
 *   GET  /status    - Get connection status
 */

// CommonJS-style import for whatsapp-web.js (it's not ESM compatible)
import pkg from 'whatsapp-web.js';
const { Client, LocalAuth } = pkg;
import qrcode from 'qrcode-terminal';
import express from 'express';

import path from 'path';
import os from 'os';

// Initialize WhatsApp client with persistent auth
// ISOLATED MODE: Headless, no visible browser — pure background service for ARIA
const client = new Client({
    authStrategy: new LocalAuth({
        dataPath: path.join(os.homedir(), '.whatsapp-aria')  // Persistent session storage
    }),
    puppeteer: {
        args: [
            '--no-sandbox',
            '--disable-setuid-sandbox',
            '--disable-gpu',
            '--disable-dev-shm-usage',
            '--no-first-run',
            '--disable-extensions',
            '--disable-default-apps',
            '--disable-sync',
            '--disable-translate',
            '--disable-background-networking',
            '--disable-component-update',
            '--disable-infobars',          // No "controlled by automation" bar
            '--hide-scrollbars',            // Clean look
            '--window-size=1280,900'
        ],
        headless: false  // Visible window — whatsapp-web.js shows only WhatsApp (single tab, no nav)
    }
});

// Express server for HTTP API
const app = express();
app.use(express.json());

let isReady = false;
let qrCode = null;
let isReconnecting = false;

// ═══════════════════════════════════════════════════════════════════════════════
// WhatsApp Client Events
// ═══════════════════════════════════════════════════════════════════════════════

client.on('qr', (qr) => {
    console.log('📱 Scan this QR code with WhatsApp:');
    qrcode.generate(qr, { small: true });
    qrCode = qr;
});

client.on('ready', () => {
    console.log('✅ WhatsApp client is ready!');
    isReady = true;
    qrCode = null;
});

client.on('authenticated', () => {
    console.log('🔐 Authenticated successfully');
});

client.on('auth_failure', (msg) => {
    console.error('❌ Authentication failed:', msg);
});

client.on('disconnected', async (reason) => {
    console.log('📴 Disconnected:', reason);
    isReady = false;
    // Auto-reconnect
    reconnect();
});

async function reconnect() {
    if (isReconnecting) return;
    isReconnecting = true;
    console.log('🔄 Auto-reconnecting WhatsApp client...');
    try {
        await client.destroy().catch(() => { });
        await new Promise(r => setTimeout(r, 3000));
        await client.initialize();
        console.log('✅ Reconnected successfully');
    } catch (e) {
        console.error('❌ Reconnect failed:', e.message);
        // Try once more after longer delay
        setTimeout(async () => {
            try {
                await client.destroy().catch(() => { });
                await new Promise(r => setTimeout(r, 5000));
                await client.initialize();
                console.log('✅ Reconnected on second attempt');
            } catch (e2) {
                console.error('❌ Second reconnect attempt failed:', e2.message);
            }
            isReconnecting = false;
        }, 10000);
        return;
    }
    isReconnecting = false;
}

client.on('message', async (msg) => {
    console.log(`📨 Message from ${msg.from}: ${msg.body}`);

    // Auto-reply example (optional)
    // if (msg.body === 'ping') {
    //     msg.reply('pong');
    // }
});

// ═══════════════════════════════════════════════════════════════════════════════
// HTTP API Endpoints
// ═══════════════════════════════════════════════════════════════════════════════

// Get status
app.get('/status', (req, res) => {
    res.json({
        ready: isReady,
        reconnecting: isReconnecting,
        hasQr: qrCode !== null,
        qr: qrCode
    });
});

// Manual reconnect/restart endpoint
app.post('/restart', async (req, res) => {
    console.log('🔄 Manual restart requested...');
    res.json({ status: 'restarting' });
    reconnect();
});

// List recent chats
app.get('/chats', async (req, res) => {
    if (!isReady) {
        return res.status(503).json({ error: 'WhatsApp not ready' });
    }

    try {
        const chats = await client.getChats();
        const chatList = chats.map(chat => ({
            id: chat.id._serialized,
            name: chat.name,
            isGroup: chat.isGroup,
            unreadCount: chat.unreadCount
        }));
        res.json({ chats: chatList });
    } catch (error) {
        res.status(500).json({ error: error.message });
    }
});

// List all contacts
app.get('/contacts', async (req, res) => {
    if (!isReady) {
        return res.status(503).json({ error: 'WhatsApp not ready' });
    }

    try {
        const contacts = await client.getContacts();
        const contactList = contacts
            .filter(c => c.isMyContact || c.name)
            .map(c => ({
                id: c.id._serialized,
                name: c.name || c.pushname || c.number,
                isMyContact: c.isMyContact,
                isGroup: c.isGroup
            }));
        res.json({ contacts: contactList });
    } catch (error) {
        res.status(500).json({ error: error.message });
    }
});

// Search for a contact/chat
app.post('/search', async (req, res) => {
    if (!isReady) {
        return res.status(503).json({ error: 'WhatsApp not ready' });
    }

    const { query } = req.body;
    if (!query) {
        return res.status(400).json({ error: 'Missing query parameter' });
    }

    try {
        const chats = await client.getChats();
        const matches = chats.filter(chat =>
            chat.name?.toLowerCase().includes(query.toLowerCase())
        ).slice(0, 10).map(chat => ({
            id: chat.id._serialized,
            name: chat.name,
            isGroup: chat.isGroup
        }));

        res.json({ matches });
    } catch (error) {
        res.status(500).json({ error: error.message });
    }
});

// Send a message (text, media, stickers)
app.post('/send', async (req, res) => {
    if (!isReady) {
        return res.status(503).json({ error: 'WhatsApp not ready' });
    }

    const { to, message, searchName, mediaPath, mediaUrl, sendAsSticker } = req.body;
    console.log(`📤 Send request: to=${to}, searchName=${searchName}, message=${message}, media=${mediaPath || mediaUrl || 'none'}`);

    try {
        let chatId = to;

        // If searchName is provided, find the chat by name
        if (searchName && !to) {
            const chats = await client.getChats();
            const match = chats.find(chat =>
                chat.name?.toLowerCase().includes(searchName.toLowerCase())
            );
            if (!match) {
                console.log(`❌ Chat not found: ${searchName}`);
                return res.status(404).json({ error: `Chat not found: ${searchName}` });
            }
            chatId = match.id._serialized;
            console.log(`✅ Found chat: ${match.name} -> ${chatId}`);
        }

        if (!chatId) {
            return res.status(400).json({ error: 'Missing "to" or "searchName" parameter' });
        }

        // Format phone number if needed
        if (!chatId.includes('@')) {
            const cleanNumber = chatId.replace(/[^0-9]/g, '');
            chatId = `${cleanNumber}@c.us`;
        }

        // Handle media sending
        if (mediaPath || mediaUrl) {
            let media;
            if (mediaPath) {
                // Validate file exists and is non-empty
                const fs = await import('fs');
                if (!fs.existsSync(mediaPath)) {
                    return res.status(400).json({ error: `File not found: ${mediaPath}` });
                }
                const stat = fs.statSync(mediaPath);
                if (stat.size === 0) {
                    return res.status(400).json({ error: `File is empty (0 bytes): ${mediaPath}` });
                }
                // Local file (PDF, image, etc.)
                const { MessageMedia } = pkg;
                media = MessageMedia.fromFilePath(mediaPath);
                console.log(`📎 Attached file: ${mediaPath} (${media.mimetype}, ${stat.size} bytes)`);

            } else if (mediaUrl) {
                // URL (GIF, online image, etc.)
                const { MessageMedia } = pkg;
                media = await MessageMedia.fromUrl(mediaUrl, { unsafeMime: true });
                console.log(`📎 Attached URL: ${mediaUrl} (${media.mimetype})`);
            }

            const options = {};
            if (message) options.caption = message;
            if (sendAsSticker) options.sendMediaAsSticker = true;
            // Auto-detect GIFs and send as animated
            if (media.mimetype === 'image/gif' || (mediaPath && mediaPath.endsWith('.gif')) || (mediaUrl && mediaUrl.includes('.gif'))) {
                options.sendMediaAsGif = true;
                console.log(`🎞️ Detected GIF - sending as animated`);
            }

            console.log(`📤 Sending media to ${chatId}`);
            const result = await client.sendMessage(chatId, media, options);
            console.log(`✅ Media sent, result:`, result ? result.id : 'no result');
            res.json({ success: true, sent: { to: chatId, type: sendAsSticker ? 'sticker' : 'media', message: message || '' } });
        } else {
            // Plain text message
            if (!message) {
                return res.status(400).json({ error: 'Missing message parameter' });
            }
            console.log(`📤 Sending to ${chatId}: "${message}"`);
            const result = await client.sendMessage(chatId, message);
            console.log(`✅ Message sent, result:`, result ? result.id : 'no result');
            res.json({ success: true, sent: { to: chatId, message } });
        }

    } catch (error) {
        console.error(`❌ Send error:`, error);
        // Auto-reconnect on detached frame errors
        if (error.message && error.message.includes('detached Frame')) {
            console.log('🔄 Detached frame detected, triggering reconnect...');
            reconnect();
        }
        res.status(500).json({ error: error.message });
    }
});

// Get messages from a chat
app.get('/messages/:chatId', async (req, res) => {
    if (!isReady) {
        return res.status(503).json({ error: 'WhatsApp not ready' });
    }

    try {
        const chat = await client.getChatById(req.params.chatId);
        const messages = await chat.fetchMessages({ limit: 20 });
        const msgList = messages.map(msg => ({
            id: msg.id._serialized,
            from: msg.from,
            body: msg.body,
            timestamp: msg.timestamp,
            fromMe: msg.fromMe,
            hasMedia: msg.hasMedia,
            type: msg.type
        }));
        res.json({ success: true, messages: msgList });
    } catch (error) {
        res.status(500).json({ success: false, error: error.message });
    }
});

// Send a GIF using WhatsApp's built-in GIF search (Tenor)
// Automates the WhatsApp Web UI: emoji button → GIF tab → search → click result → send
// Usage: { searchName: "KRACK", query: "happy cat" }

// Debug: inspect page selectors (temporary)
app.get('/debug-page', async (req, res) => {
    const page = client.pupPage;
    if (!page) return res.json({ error: 'no page' });
    try {
        const results = await page.evaluate(() => {
            const found = {};
            // Get ALL footer buttons with details
            const footerBtns = document.querySelectorAll('footer button');
            found['footer_buttons'] = [...footerBtns].map((btn, i) => ({
                idx: i,
                ariaLabel: btn.getAttribute('aria-label'),
                title: btn.getAttribute('title'),
                dataTestid: btn.getAttribute('data-testid'),
                childIcons: [...btn.querySelectorAll('[data-icon]')].map(el => el.getAttribute('data-icon')),
                text: btn.textContent?.substring(0, 30),
                className: btn.className?.substring(0, 50)
            }));
            // Get all elements near the input area 
            const footer = document.querySelector('footer');
            if (footer) {
                found['footer_html'] = footer.innerHTML.substring(0, 500);
            }
            // All data-icons on page
            found['_all_data_icons'] = [...new Set([...document.querySelectorAll('[data-icon]')].map(el => el.getAttribute('data-icon')))];
            return found;
        });
        res.json(results);
    } catch (e) { res.json({ error: e.message }); }
});

app.post('/send-gif', async (req, res) => {
    if (!isReady) {
        return res.status(503).json({ error: 'WhatsApp not ready' });
    }

    const { searchName, query } = req.body;
    if (!query) {
        return res.status(400).json({ error: 'Missing "query" parameter (GIF search term)' });
    }
    if (!searchName) {
        return res.status(400).json({ error: 'Missing "searchName" parameter' });
    }

    console.log(`🎞️ GIF UI request: query="${query}", contact="${searchName}"`);

    // Use PURE Puppeteer for everything (no whatsapp-web.js API calls to avoid frame detach)
    const page = client.pupPage;
    if (!page) {
        return res.status(500).json({ error: 'Puppeteer page not available' });
    }

    try {
        // Close any open panels first
        try { await page.keyboard.press('Escape'); } catch (_) { }
        await new Promise(r => setTimeout(r, 300));
        try { await page.keyboard.press('Escape'); } catch (_) { }
        await new Promise(r => setTimeout(r, 500));

        // Step 1: Open chat via Store (Ultra Robust)
        console.log(`🔍 Opening chat via Store: "${searchName}"...`);

        const openResult = await page.evaluate((contactName) => {
            // Check if Store is available (it should be if whatsapp-web.js is loaded)
            if (!window.Store || !window.Store.Chat) return "Store not found";

            const chat = window.Store.Chat.models.find(c =>
                c.name === contactName ||
                c.formattedTitle === contactName ||
                (c.contact && c.contact.name === contactName)
            );

            if (chat) {
                window.Store.Cmd.openChatAt(chat);
                return "Opened";
            }
            return "Chat not found in Store";
        }, searchName);
        console.log(`   Store result: ${openResult}`);

        if (openResult !== 'Opened') {
            // Fallback to Search strategy
            console.log(`   Detailed search fallback...`);
            const searchSelectors = [
                'div[contenteditable="true"][data-tab="3"]',
                'div[role="textbox"][title="Search input textbox"]',
                'span[data-icon="search"]'
            ];

            let searchBar = null;
            for (const sel of searchSelectors) {
                searchBar = await page.$(sel);
                if (searchBar) break;
            }

            if (searchBar) {
                await searchBar.click();
                // clear previous if any
                await page.keyboard.down('Control');
                await page.keyboard.press('a');
                await page.keyboard.up('Control');
                await page.keyboard.press('Backspace');

                await page.keyboard.type(searchName, { delay: 50 });
                await new Promise(r => setTimeout(r, 2000)); // Wait for results

                // Press Enter to open top result
                await page.keyboard.press('Enter');
                console.log('   Pressed Enter to open chat');
            } else {
                // Try global shortcut
                await page.keyboard.down('Control');
                await page.keyboard.down('Alt');
                await page.keyboard.press('/');
                await page.keyboard.up('Alt');
                await page.keyboard.up('Control');
                await new Promise(r => setTimeout(r, 500));
                await page.keyboard.type(searchName, { delay: 50 });
                await new Promise(r => setTimeout(r, 2000));
                await page.keyboard.press('Enter');
            }
        }

        await new Promise(r => setTimeout(r, 2000)); // Wait for chat to open

        // Clear search if we used it (press Escape)
        try { await page.keyboard.press('Escape'); } catch (_) { }
        await new Promise(r => setTimeout(r, 500));

        // Step 2: Now the chat is open. Click the emoji button
        console.log(`🎭 Opening emoji panel...`);

        // Use the specific selector found by subagent
        const emojiSelector = 'button[aria-label="Emojis, GIFs, Stickers"]';

        try {
            await page.waitForSelector(emojiSelector, { timeout: 5000 });
        } catch (e) {
            console.log('   Emoji button not found within 5s');
            // Try fallback selector just in case
        }

        const emojiBtn = await page.$(emojiSelector);

        if (emojiBtn) {
            await emojiBtn.click();
        } else {
            // Fallback: try finding by icon path or data-icon
            const iconBtn = await page.$('span[data-icon="smiley"], span[data-icon="emoji-input"]');
            if (iconBtn) {
                await iconBtn.click();
            } else {
                return res.status(500).json({ error: 'Cannot find emoji button (tried aria-label and data-icon)' });
            }
        }
        await new Promise(r => setTimeout(r, 1000));

        // Step 3: Click the GIF tab
        console.log(`🎞️ Switching to GIF tab...`);

        // Use the specific aria-label "Gifs selector" from subagent
        const gifTabSelector = 'button[aria-label="Gifs selector"]';
        let gifTab = await page.$(gifTabSelector);

        if (gifTab) {
            await gifTab.click();
            console.log(`   Clicked GIF tab (aria-label="Gifs selector")`);
        } else {
            // Fallback strategies
            let gifTabClicked = false;
            const allBtns = await page.$$('button, [role="tab"], span');
            for (const btn of allBtns) {
                const text = await page.evaluate(el => {
                    return (el.textContent || el.getAttribute('aria-label') || '').trim();
                }, btn);
                if (text === 'GIF' || text === 'Gifs selector' || text === 'GIFs') {
                    await btn.click();
                    gifTabClicked = true;
                    console.log(`   Clicked GIF tab (text="${text}")`);
                    break;
                }
            }
            if (!gifTabClicked) {
                // Fallback: try data-testid patterns
                const gifBtn = await page.$('[data-testid="gif-btn"], [aria-label*="GIF"], [aria-label*="Gifs"]');
                if (gifBtn) {
                    await gifBtn.click();
                } else {
                    return res.status(500).json({ error: 'Cannot find GIF tab button' });
                }
            }
        }
        await new Promise(r => setTimeout(r, 1000));

        // Step 4: Type in the Tenor search box
        console.log(`🔍 Searching for: "${query}"...`);

        // Find the GIF search input
        const gifSearch = await page.$('input[placeholder*="Tenor"], input[placeholder*="GIF"], input[placeholder*="Search"]');
        if (!gifSearch) {
            // Try contenteditable div inside the GIF panel
            const divSearch = await page.$('[contenteditable][data-tab="2"]');
            if (divSearch) {
                await divSearch.click();
            } else {
                return res.status(500).json({ error: 'Cannot find GIF search input' });
            }
        } else {
            await gifSearch.click();
        }
        await new Promise(r => setTimeout(r, 300));
        await page.keyboard.type(query, { delay: 40 });
        await new Promise(r => setTimeout(r, 2500));  // Wait for Tenor results

        // Step 5: Click the first GIF result
        console.log(`👆 Clicking first GIF result...`);

        // GIF results are typically button or div elements containing images
        let gifClicked = false;

        // Try various selectors for GIF results
        const gifSelectors = [
            'button img[src*="tenor"]',
            'img[src*="tenor"]',
            'div[role="button"] img',
            'button[data-testid] img',
            'div[role="listitem"] img',
        ];

        for (const sel of gifSelectors) {
            const gifs = await page.$$(sel);
            if (gifs && gifs.length > 0) {
                // Click the parent (button/div) not the img itself
                const parent = await page.evaluateHandle(el => el.closest('button') || el.closest('[role="button"]') || el.parentElement, gifs[0]);
                if (parent) {
                    await parent.click();
                } else {
                    await gifs[0].click();
                }
                gifClicked = true;
                console.log(`   Clicked GIF using selector: ${sel} (${gifs.length} results found)`);
                break;
            }
        }

        if (!gifClicked) {
            return res.status(404).json({ error: `No GIF results found for "${query}"` });
        }
        await new Promise(r => setTimeout(r, 2000));

        // Step 6: Click send button
        console.log(`📤 Looking for send button...`);
        const sendBtn = await page.$('[data-icon="send"], [data-testid="send"], [aria-label="Send"]');
        if (sendBtn) {
            await sendBtn.click();
            console.log(`   Clicked send button`);
            await new Promise(r => setTimeout(r, 1000));
        } else {
            // In some WhatsApp versions, clicking the GIF auto-sends it
            console.log(`   No send button found - GIF may have been auto-sent`);
        }

        console.log(`✅ GIF "${query}" sent to "${searchName}" via WhatsApp UI!`);
        res.json({
            success: true,
            sent: { contact: searchName, query: query, method: 'whatsapp-gif-picker' }
        });

    } catch (error) {
        console.error(`❌ GIF UI error:`, error.message);
        // Try to close any open panels
        try { await page.keyboard.press('Escape'); } catch (_) { }
        res.status(500).json({ error: error.message });
    }
});

// ═══════════════════════════════════════════════════════════════════════════════
// Start Server
// ═══════════════════════════════════════════════════════════════════════════════

const PORT = process.env.PORT || 3001;

// Keep process alive
const _origExit = process.exit;
process.exit = function (code) {
    console.error(`⚠️ process.exit(${code}) was called! Stack:`, new Error().stack);
    // Don't actually exit — keep running
};

process.on('exit', (code) => {
    console.error(`⚠️ Process exiting with code ${code}`);
    console.error('Stack:', new Error().stack);
});

process.on('unhandledRejection', (reason, promise) => {
    console.error('⚠️ Unhandled Rejection:', reason);
});

process.on('uncaughtException', (err) => {
    console.error('⚠️ Uncaught Exception:', err.message);
});

// Explicit keepalive — prevents Node from exiting even if all other refs are cleared
const keepAlive = setInterval(() => { }, 60000);

app.listen(PORT, () => {
    console.log(`\n🚀 ARIA WhatsApp Bridge running on http://localhost:${PORT}`);
    console.log(`\nEndpoints:`);
    console.log(`  GET  /status        - Check connection status`);
    console.log(`  GET  /chats         - List recent chats`);
    console.log(`  POST /search        - Search for chat by name`);
    console.log(`  POST /send          - Send message/media`);
    console.log(`  POST /send-gif      - Search & send GIF via Tenor`);
    console.log(`  GET  /messages/:id  - Get messages from chat\n`);
});

// Initialize WhatsApp client with retry
async function initWithRetry(maxRetries = 3) {
    for (let attempt = 1; attempt <= maxRetries; attempt++) {
        try {
            console.log(`🔄 Initializing WhatsApp client (attempt ${attempt}/${maxRetries})...`);
            await client.initialize();
            console.log('✅ Client initialized successfully');
            return;
        } catch (err) {
            console.error(`❌ Attempt ${attempt} failed:`, err.message);
            if (attempt < maxRetries) {
                const delay = attempt * 5000;
                console.log(`⏳ Retrying in ${delay / 1000}s...`);
                await new Promise(resolve => setTimeout(resolve, delay));
            } else {
                console.error('❌ All initialization attempts failed. Bridge will stay running for manual retry.');
                console.error('   You can restart the bridge to try again.');
            }
        }
    }
}

initWithRetry();
