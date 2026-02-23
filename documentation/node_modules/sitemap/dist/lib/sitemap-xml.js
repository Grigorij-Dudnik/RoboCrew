"use strict";
/*!
 * Sitemap
 * Copyright(c) 2011 Eugene Kalinin
 * MIT Licensed
 */
Object.defineProperty(exports, "__esModule", { value: true });
exports.element = exports.ctag = exports.otag = exports.text = void 0;
const errors_1 = require("./errors");
/**
 * Regular expression matching invalid XML 1.0 Unicode characters that must be removed.
 *
 * Based on the XML 1.0 specification (https://www.w3.org/TR/xml/#charsets):
 * - Control characters (U+0000-U+001F except tab, newline, carriage return)
 * - Delete character (U+007F)
 * - Invalid control characters (U+0080-U+009F except U+0085)
 * - Surrogate pairs (U+D800-U+DFFF)
 * - Non-characters (permanently reserved code points)
 *
 * @see https://www.w3.org/TR/xml/#charsets
 */
const invalidXMLUnicodeRegex = 
// eslint-disable-next-line no-control-regex
/[\u0000-\u0008\u000B\u000C\u000E-\u001F\u007F-\u0084\u0086-\u009F\uD800-\uDFFF\uFDD0-\uFDDF\u{1FFFE}-\u{1FFFF}\u{2FFFE}-\u{2FFFF}\u{3FFFE}-\u{3FFFF}\u{4FFFE}-\u{4FFFF}\u{5FFFE}-\u{5FFFF}\u{6FFFE}-\u{6FFFF}\u{7FFFE}-\u{7FFFF}\u{8FFFE}-\u{8FFFF}\u{9FFFE}-\u{9FFFF}\u{AFFFE}-\u{AFFFF}\u{BFFFE}-\u{BFFFF}\u{CFFFE}-\u{CFFFF}\u{DFFFE}-\u{DFFFF}\u{EFFFE}-\u{EFFFF}\u{FFFFE}-\u{FFFFF}\u{10FFFE}-\u{10FFFF}]/gu;
/**
 * Regular expressions for XML entity escaping
 */
const amp = /&/g;
const lt = /</g;
const gt = />/g;
const apos = /'/g;
const quot = /"/g;
/**
 * Valid XML attribute name pattern. XML names must:
 * - Start with a letter, underscore, or colon
 * - Contain only letters, digits, hyphens, underscores, colons, or periods
 *
 * @see https://www.w3.org/TR/xml/#NT-Name
 */
const validAttributeNameRegex = /^[a-zA-Z_:][\w:.-]*$/;
/**
 * Validates that an attribute name is a valid XML identifier.
 *
 * @param name - The attribute name to validate
 * @throws {InvalidXMLAttributeNameError} If the attribute name is invalid
 */
function validateAttributeName(name) {
    if (!validAttributeNameRegex.test(name)) {
        throw new errors_1.InvalidXMLAttributeNameError(name);
    }
}
/**
 * Escapes text content for safe inclusion in XML text nodes.
 *
 * Security Model:
 * - Escapes & → &amp; (required to prevent entity interpretation)
 * - Escapes < → &lt; (required to prevent tag injection)
 * - Escapes > → &gt; (defense-in-depth, prevents CDATA injection)
 * - Removes invalid XML Unicode characters per XML 1.0 spec
 *
 * @param txt - The text content to escape
 * @returns XML-safe escaped text with invalid characters removed
 * @throws {TypeError} If txt is not a string
 */
function text(txt) {
    if (typeof txt !== 'string') {
        throw new TypeError(`text() requires a string, received ${typeof txt}: ${String(txt)}`);
    }
    return txt
        .replace(amp, '&amp;')
        .replace(lt, '&lt;')
        .replace(gt, '&gt;')
        .replace(invalidXMLUnicodeRegex, '');
}
exports.text = text;
/**
 * Generates an opening XML tag with optional attributes.
 *
 * Security Model:
 * - Validates attribute names to prevent injection via malformed names
 * - Escapes all attribute values with proper XML entity encoding
 * - Escapes &, <, >, ", and ' in attribute values
 * - Removes invalid XML Unicode characters
 *
 * @param nodeName - The XML element name
 * @param attrs - Optional object mapping attribute names to string values
 * @param selfClose - If true, generates a self-closing tag
 * @returns Opening XML tag string
 * @throws {InvalidXMLAttributeNameError} If an attribute name contains invalid characters
 * @throws {TypeError} If attrs values are not strings
 */
function otag(nodeName, attrs, selfClose = false) {
    let attrstr = '';
    for (const k in attrs) {
        // Validate attribute name to prevent injection
        validateAttributeName(k);
        const attrValue = attrs[k];
        if (typeof attrValue !== 'string') {
            throw new TypeError(`otag() attribute "${k}" value must be a string, received ${typeof attrValue}: ${String(attrValue)}`);
        }
        // Escape attribute value with full entity encoding
        const val = attrValue
            .replace(amp, '&amp;')
            .replace(lt, '&lt;')
            .replace(gt, '&gt;')
            .replace(apos, '&apos;')
            .replace(quot, '&quot;')
            .replace(invalidXMLUnicodeRegex, '');
        attrstr += ` ${k}="${val}"`;
    }
    return `<${nodeName}${attrstr}${selfClose ? '/' : ''}>`;
}
exports.otag = otag;
/**
 * Generates a closing XML tag.
 *
 * @param nodeName - The XML element name
 * @returns Closing XML tag string
 * @throws {TypeError} If nodeName is not a string
 */
function ctag(nodeName) {
    if (typeof nodeName !== 'string') {
        throw new TypeError(`ctag() nodeName must be a string, received ${typeof nodeName}: ${String(nodeName)}`);
    }
    return `</${nodeName}>`;
}
exports.ctag = ctag;
function element(nodeName, attrs, innerText) {
    if (typeof attrs === 'string') {
        // Pattern 1: element(nodeName, textContent)
        return otag(nodeName) + text(attrs) + ctag(nodeName);
    }
    else if (innerText !== undefined) {
        // Pattern 2: element(nodeName, attrs, textContent)
        return otag(nodeName, attrs) + text(innerText) + ctag(nodeName);
    }
    else {
        // Pattern 3: element(nodeName, attrs) - self-closing
        return otag(nodeName, attrs, true);
    }
}
exports.element = element;
