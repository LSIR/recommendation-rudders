/**
 * @license
 * Copyright Google LLC All Rights Reserved.
 *
 * Use of this source code is governed by an Apache2 license that can be
 * found in the LICENSE file.
 */
import { Inject, Injectable } from '@angular/core';
import { VertexPalm2LLM } from '../lib/text-templates/llm_vertexapi_palm2';

// TODO: Unclear to me if this is needed or helpful...
//
// The value of having a service here is that the same LLM object can be used
// throughout the app.
@Injectable({
  providedIn: 'root'
})
export class PalmApiService {
  constructor(@Inject('llm') private llm: VertexPalm2LLM) { }
}
