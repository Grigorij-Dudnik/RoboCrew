"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.xmlLint = void 0;
const fs_1 = require("fs");
const node_path_1 = require("node:path");
const child_process_1 = require("child_process");
const errors_1 = require("./errors");
/**
 * Finds the `schema` directory with robust path resolution.
 * Searches from the project root directory using process.cwd().
 * This works correctly regardless of whether the code is running from:
 * - Source: lib/xmllint.ts
 * - ESM build: dist/esm/lib/xmllint.js
 * - CJS build: dist/cjs/lib/xmllint.js
 * - Test environment
 *
 * @throws {Error} if the schema directory is not found
 * @returns {string} the path to the schema directory
 */
function findSchemaDir() {
    // Search for schema directory from project root
    // This works in test, build, and source environments
    const possiblePaths = [
        (0, node_path_1.resolve)(process.cwd(), 'schema'),
        (0, node_path_1.resolve)(process.cwd(), '..', 'schema'),
        (0, node_path_1.resolve)(process.cwd(), '..', '..', 'schema'), // Two levels up
    ];
    for (const schemaPath of possiblePaths) {
        if ((0, fs_1.existsSync)(schemaPath)) {
            return schemaPath;
        }
    }
    throw new Error(`Schema directory not found. Searched paths: ${possiblePaths.join(', ')}`);
}
/**
 * Verify the passed in xml is valid. Requires xmllib be installed
 *
 * Security: This function always pipes XML content via stdin to prevent
 * command injection vulnerabilities. Never pass user-controlled strings
 * as file path arguments to xmllint.
 *
 * @param xml what you want validated (string or Readable stream)
 * @return {Promise<void>} resolves on valid rejects [error stderr]
 */
function xmlLint(xml) {
    const args = [
        '--schema',
        (0, node_path_1.resolve)(findSchemaDir(), 'all.xsd'),
        '--noout',
        '-', // Always read from stdin for security
    ];
    return new Promise((resolve, reject) => {
        (0, child_process_1.execFile)('which', ['xmllint'], (error, stdout, stderr) => {
            if (error) {
                reject([new errors_1.XMLLintUnavailable()]);
                return;
            }
            const xmllint = (0, child_process_1.execFile)('xmllint', args, (error, stdout, stderr) => {
                if (error) {
                    reject([error, stderr]);
                }
                resolve();
            });
            // Always pipe XML content via stdin for security
            if (xmllint.stdin) {
                if (typeof xml === 'string') {
                    // Convert string to stream and pipe to stdin
                    xmllint.stdin.write(xml);
                    xmllint.stdin.end();
                }
                else if (xml) {
                    // Pipe readable stream to stdin
                    xml.pipe(xmllint.stdin);
                }
            }
            if (xmllint.stdout) {
                xmllint.stdout.unpipe();
            }
        });
    });
}
exports.xmlLint = xmlLint;
