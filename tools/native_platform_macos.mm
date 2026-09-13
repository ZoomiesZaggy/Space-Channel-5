// SPDX-License-Identifier: GPL-2.0-or-later
#import <Foundation/Foundation.h>
#include <string>
#include <cstdarg>
#include <cstdio>
int darw_printf(const char *format,...){
 va_list args;va_start(args,format);int count=vfprintf(stderr,format,args);va_end(args);return count;
}
std::string os_PrecomposedString(std::string value){
 @autoreleasepool {
  NSString *text=[NSString stringWithUTF8String:value.c_str()];
  const char *normalized=[[text precomposedStringWithCanonicalMapping] UTF8String];
  return normalized?normalized:value;
 }
}
namespace hostfs {
std::string getScreenshotsPath(){
 @autoreleasepool {
  NSArray *paths=NSSearchPathForDirectoriesInDomains(NSPicturesDirectory,NSUserDomainMask,YES);
  return paths.count?[[paths objectAtIndex:0] UTF8String]:".";
 }
}
namespace i18n {
std::string getSystemLocale(){
 @autoreleasepool {
  NSArray *languages=[NSLocale preferredLanguages];
  return languages.count?[[languages objectAtIndex:0] UTF8String]:"en";
 }
}
