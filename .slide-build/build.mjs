import fs from 'node:fs/promises';
import {Presentation, PresentationFile} from 'file:///C:/Users/Lenovo/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/@oai/artifact-tool/dist/artifact_tool.mjs';
import {finalizePresentation} from 'file:///C:/Users/Lenovo/.codex/plugins/cache/openai-primary-runtime/presentations/26.909.12148/skills/presentations/container_tools/artifact_tool_utils.mjs';
const root='C:/Users/Lenovo/OneDrive/Desktop/Nyaya Vault';
const skill='C:/Users/Lenovo/.codex/plugins/cache/openai-primary-runtime/presentations/26.909.12148/skills/presentations';
const p=Presentation.create({slideSize:{width:1600,height:900}});
const s=p.slides.add();
s.background.fill='linear(0deg, #F9D8BC 0%, #FFF9F3 50%, #F9D8BC 100%)';
function rect(x,y,w,h,fill,line='none',lw=0){return s.shapes.add({geometry:'rect',position:{left:x,top:y,width:w,height:h},fill,line:{fill:line,width:lw}});}
function txt(text,x,y,w,h,size,bold=false,font='Arial',color='#171717'){let a=rect(x,y,w,h,'none');a.text=text;a.text.style={typeface:font,fontSize:size,bold,color,autoFit:'none'};return a;}
txt('NYAYA VAULT',55,38,300,45,24,true,'Arial','#744E38');
txt('IMPACT AND BENEFITS',450,30,1000,75,52);
txt('IMPACT',56,138,400,40,26,true,'Arial','#744E38');
txt('BENEFITS',56,499,400,40,26,true,'Arial','#744E38');
const cards=[
['Faster\nInvestigations','OCR and semantic search find case evidence in seconds instead of hours.','#FAD09F'],
['Court-Ready\nEvidence','Auto-generated Section 63 BSA certificates and hash checks make evidence admissible.','#FFF0C3'],
['Tamper-Proof\nRecords','A blockchain-anchored audit trail proves no record was altered.','#D8E9CF'],
['Victim Privacy\nProtected','Redaction, approved by an officer, hides the identities of victims and witnesses.','#CCDDF3'],
['Secure Access\nControl','Role, case-assignment and clearance checks keep evidence limited to authorised officers.','#C6D9F4'],
['AI-Assisted\nWork','An AI assistant and entity extraction cut manual reading and paperwork.','#D4C5E7'],
['Inclusive &\nMultilingual','Works in 6 Indian languages on both desktop and mobile.','#D1E5DC'],
['Low Cost,\nEasy to Scale','Mostly open-source and deployable one department at a time.','#F3D1C9']
];
cards.forEach(([title,body,color],i)=>{let x=56+(i%4)*378,y=i<4?192:553;
rect(x+3,y+5,354,280,'#CBBFB5');rect(x,y,354,280,'#FFFFFF','#B8ADA5',1);rect(x+8,y+8,338,264,color);
txt(String(i+1).padStart(2,'0'),x+21,y+20,96,92,60,false,'Arial');
txt(title,x+115,y+28,220,83,27,true);
txt(body,x+24,y+125,307,133,24,false,'Georgia');
});
s.speakerNotes.textFrame.setText('Text supplied by the user, reproduced as requested. Visual design inspired by the attached reference image.');
await (await PresentationFile.exportPptx(p)).save(root+'/.slide-build/candidate.pptx');
const png=await p.export({slide:s,format:'png',scale:1});await fs.writeFile(root+'/output/impact-and-benefits.png',new Uint8Array(await png.arrayBuffer()));
await finalizePresentation({workspaceDir:root,candidatePath:root+'/.slide-build/candidate.pptx',finalPath:root+'/output/impact-and-benefits-final.pptx',pythonExecutable:'C:/Users/Lenovo/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe',integrityValidatorPath:skill+'/container_tools/inspect_presentation_package_integrity.py',layoutValidatorPath:skill+'/container_tools/inspect_presentation_layout_geometry.py',layoutArgs:['--expected-slide-size-emu','15240000,8572500','--validate-heading-fit'],explicitTotalSlideCount:1,fontPolicy:{basis:'design',families:['Arial','Arial Narrow','Georgia']},verifyArtifactToolImport:true,receiptPath:root+'/.slide-build/validation-final.json'});
console.log('Complete');



