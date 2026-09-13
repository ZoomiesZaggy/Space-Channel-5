// SPDX-License-Identifier: GPL-2.0-or-later
#pragma once
#include "rend/gles/gles.h"
#include "rend/gles/glcache.h"
#include "hw/pvr/ta_ctx.h"
#include <cmath>
#include <iostream>
#include <fstream>

// Interpolate only matching submitted geometry. Topology changes and large
// discontinuities fall back to the original frame; game state is never changed.
class NativeMotionRenderer : public OpenGLRenderer {
 std::vector<Vertex> previous;
 std::vector<u32> indices;
 std::vector<PolyParam> previousLists[3];
 unsigned interpolated=0,rejected=0;
 static bool sameMaterial(const PolyParam &a,const PolyParam &b){
  return a.count==b.count && a.tsp.full==b.tsp.full && a.tcw.full==b.tcw.full && a.pcw.full==b.pcw.full && a.isp.full==b.isp.full && a.tileclip==b.tileclip;
 }

public:
 std::unique_ptr<GlFramebuffer> midpoint;
 bool midpointReady=false;
 bool Render() override {
  auto &context=*gl.rendContext;
  if(context.isRTT)return OpenGLRenderer::Render();
  const auto current=context.verts;
  const std::vector<PolyParam> *lists[]={&context.global_param_op,&context.global_param_pt,&context.global_param_tr};
  std::vector<int> matches(current.size(),-1);
  size_t moving=0;
  if(context.modtrig.empty())for(unsigned list=0;list<3;list++)for(const auto &poly:*lists[list]){
   const PolyParam *match=nullptr;
   for(const auto &candidate:previousLists[list])if(sameMaterial(poly,candidate)){
    if(match){match=nullptr;break;}match=&candidate;
   }
   if(!match || poly.first+poly.count>context.idx.size() || match->first+match->count>indices.size())continue;
   bool valid=true;std::vector<std::pair<u32,u32>> pairs;
   for(u32 k=0;k<poly.count;k++){
    u32 now=context.idx[poly.first+k],before=indices[match->first+k];
    if(now==0xffffffffu && before==now)continue;
    if(now>=current.size() || before>=previous.size()){valid=false;break;}
    if(now<4 || before<4){valid=false;break;}
    const auto &a=previous[before],&b=current[now];
    if(!std::isfinite(a.x+a.y+a.z+b.x+b.y+b.z) || a.z<=0 || b.z<=0 ||
       std::abs(a.x-b.x)>80 || std::abs(a.y-b.y)>80 || a.z/b.z<0.5f || a.z/b.z>2.f ||
       a.u!=b.u || a.v!=b.v){valid=false;break;}
    pairs.emplace_back(now,before);
   }
   if(valid)for(auto pair:pairs)matches[pair.first]=pair.second;
  }
  for(size_t j=0;j<current.size();j++)if(matches[j]>=0){
   const auto &a=previous[matches[j]],&b=current[j];
   if(a.x!=b.x || a.y!=b.y || a.z!=b.z)moving++;
  }
  midpointReady=false;
  if(moving){
   for(size_t j=0;j<current.size();j++){
    if(matches[j]<0)continue;
    auto &v=context.verts[j];const auto &p=previous[matches[j]];
    // Positions arrive after perspective projection; interpolate in that space.
    v.x=(v.x+p.x)*.5f;v.y=(v.y+p.y)*.5f;v.z=(v.z+p.z)*.5f;
   }
   OpenGLRenderer::Render();
   auto *frame=gl.ofbo2.ready?gl.ofbo2.framebuffer.get():gl.ofbo.framebuffer.get();
   if(frame){
    if(!midpoint || midpoint->getWidth()!=frame->getWidth() || midpoint->getHeight()!=frame->getHeight())
     midpoint=std::make_unique<GlFramebuffer>(frame->getWidth(),frame->getHeight());
    frame->bind(GL_READ_FRAMEBUFFER);midpoint->bind(GL_DRAW_FRAMEBUFFER);
    glcache.Disable(GL_SCISSOR_TEST);
    glBlitFramebuffer(0,0,frame->getWidth(),frame->getHeight(),0,0,frame->getWidth(),frame->getHeight(),GL_COLOR_BUFFER_BIT,GL_NEAREST);
    glBindFramebuffer(GL_FRAMEBUFFER,0);midpointReady=true;interpolated++;
    if(interpolated==100)if(const char *path=std::getenv("SC5_MOTION_CAPTURE")){
     const int w=midpoint->getWidth(),h=midpoint->getHeight();
     std::vector<unsigned char> pixels(w*h*3);midpoint->bind(GL_READ_FRAMEBUFFER);
     glPixelStorei(GL_PACK_ALIGNMENT,1);glReadPixels(0,0,w,h,GL_RGB,GL_UNSIGNED_BYTE,pixels.data());
     std::ofstream file(path,std::ios::binary);file<<"P6\n"<<w<<" "<<h<<"\n255\n";
     file.write(reinterpret_cast<const char*>(pixels.data()),pixels.size());glBindFramebuffer(GL_FRAMEBUFFER,0);
    }
   }
   context.verts=current;
  }else rejected++;
  previous=current;indices=context.idx;
  for(unsigned j=0;j<3;j++)previousLists[j]=*lists[j];
  return OpenGLRenderer::Render();
 }
 void Term() override {
  std::cout<<"Native motion interpolation generated="<<interpolated<<" fallback="<<rejected<<"\n";
  midpoint.reset();OpenGLRenderer::Term();
 }
};
