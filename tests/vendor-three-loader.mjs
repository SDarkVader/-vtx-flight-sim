import {pathToFileURL} from 'node:url';
import {resolve as pathResolve} from 'node:path';
export async function resolve(specifier, context, nextResolve) {
  if (specifier === 'three')
    return {url:pathToFileURL(pathResolve('public/vendor/three.module.js')).href,shortCircuit:true};
  if (specifier.startsWith('three/addons/'))
    return {url:pathToFileURL(pathResolve('public/vendor',specifier.slice('three/addons/'.length))).href,shortCircuit:true};
  return nextResolve(specifier,context);
}
