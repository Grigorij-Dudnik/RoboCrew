/*!
 * Sitemap
 * Copyright(c) 2011 Eugene Kalinin
 * MIT Licensed
 */
import { TagNames } from './types';
import { StringObj } from './sitemap-item-stream';
import { IndexTagNames } from './sitemap-index-stream';
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
export declare function text(txt: string): string;
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
export declare function otag(nodeName: TagNames | IndexTagNames, attrs?: StringObj, selfClose?: boolean): string;
/**
 * Generates a closing XML tag.
 *
 * @param nodeName - The XML element name
 * @returns Closing XML tag string
 * @throws {TypeError} If nodeName is not a string
 */
export declare function ctag(nodeName: TagNames | IndexTagNames): string;
/**
 * Generates a complete XML element with optional attributes and text content.
 *
 * Supports three usage patterns via function overloading:
 * 1. Element with text content: element('loc', 'https://example.com')
 * 2. Element with attributes and text: element('video:player_loc', { autoplay: 'ap=1' }, 'https://...')
 * 3. Self-closing element with attributes: element('image:image', { href: '...' })
 *
 * @param nodeName - The XML element name
 * @param attrs - Either a string (text content) or object (attributes)
 * @param innerText - Optional text content when attrs is an object
 * @returns Complete XML element string
 * @throws {InvalidXMLAttributeNameError} If an attribute name contains invalid characters
 * @throws {TypeError} If arguments have invalid types
 */
export declare function element(nodeName: TagNames, attrs: StringObj, innerText: string): string;
export declare function element(nodeName: TagNames | IndexTagNames, innerText: string): string;
export declare function element(nodeName: TagNames, attrs: StringObj): string;
