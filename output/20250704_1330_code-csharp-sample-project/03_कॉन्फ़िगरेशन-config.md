> Previously, we looked at [आइटम मॉडल (Item Model)](02_आइटम-मॉडल-item-model.md).

# Chapter 2: कॉन्फ़िगरेशन (Config)
Let's begin exploring this concept. इस अध्याय में, हम `20250704_1330_code-csharp-sample-project` में कॉन्फ़िगरेशन (Config) के बारे में जानेंगे। हमारा लक्ष्य यह समझना है कि एप्लीकेशन की सेटिंग्स को कैसे प्रबंधित किया जाता है और कैसे इनका उपयोग कोड में किया जाता है।
**कॉन्फ़िगरेशन का महत्व**
सोचिए आपके पास एक रसोई है। रसोई में, आपको अलग-अलग व्यंजन बनाने के लिए अलग-अलग सेटिंग्स की आवश्यकता होती है। उदाहरण के लिए, केक बनाने के लिए आपको एक विशिष्ट तापमान और समय की आवश्यकता होती है, जबकि चावल बनाने के लिए आपको अलग तापमान और समय की आवश्यकता होती है। इसी तरह, एक एप्लीकेशन को विभिन्न परिस्थितियों में सही ढंग से काम करने के लिए कॉन्फ़िगरेशन की आवश्यकता होती है। कॉन्फ़िगरेशन एप्लीकेशन को बताता है कि डेटा कहाँ से प्राप्त करना है, प्रोसेसिंग को कैसे करना है, और अन्य महत्वपूर्ण सेटिंग्स। यह एप्लीकेशन को अधिक लचीला और अनुकूलनीय बनाता है।  अगर हम सीधे कोड में सेटिंग्स डालते, तो उन्हें बदलना मुश्किल हो जाता। कॉन्फ़िगरेशन हमें बिना कोड बदले सेटिंग्स बदलने की अनुमति देता है।
**मुख्य अवधारणाएँ**
इस प्रोजेक्ट में, कॉन्फ़िगरेशन को `AppConfig.cs` फ़ाइल में परिभाषित किया गया है। यह फ़ाइल एप्लीकेशन की सभी महत्वपूर्ण सेटिंग्स को स्टोर करती है, जैसे कि डेटा फ़ाइल का पाथ (`DataFilePath`) और प्रोसेसिंग की सीमा (`ProcessingThreshold`)।
*   **डेटा फ़ाइल पाथ (`DataFilePath`):** यह बताता है कि एप्लीकेशन को डेटा कहाँ से लोड करना है। इस उदाहरण में, यह "data/items.json" है।
*   **प्रोसेसिंग थ्रेशोल्ड (`ProcessingThreshold`):** यह एक सीमा है जिसका उपयोग प्रोसेसिंग के दौरान किया जाता है। इस उदाहरण में, यह 100 है।
*   **लॉग लेवल (`LogLevel`):** यह लॉगिंग की गंभीरता को निर्धारित करता है। उदाहरण के लिए, "INFO", "DEBUG", या "ERROR"।
**उपयोग और कार्यप्रणाली**
`AppConfig.cs` फ़ाइल एक `static class` है, जिसका मतलब है कि हम इसके सदस्यों को सीधे क्लास नाम से एक्सेस कर सकते हैं, बिना क्लास का ऑब्जेक्ट बनाए। यह निम्नलिखित तरीके प्रदान करता है:
*   `GetDataPath()`: यह डेटा फ़ाइल का पाथ प्रदान करता है।
*   `GetThreshold()`: यह प्रोसेसिंग थ्रेशोल्ड प्रदान करता है।
इन तरीकों का उपयोग एप्लीकेशन के अन्य हिस्सों में कॉन्फ़िगरेशन सेटिंग्स प्राप्त करने के लिए किया जाता है। उदाहरण के लिए, `DataHandler` क्लास डेटा फ़ाइल के पाथ को प्राप्त करने के लिए `AppConfig.GetDataPath()` का उपयोग कर सकता है। `ItemProcessor` क्लास प्रोसेसिंग थ्रेशोल्ड प्राप्त करने के लिए `AppConfig.GetThreshold()` का उपयोग कर सकता है।
**कोड उदाहरण**
यहाँ `AppConfig.cs` फ़ाइल का कोड दिया गया है:
```csharp
// tests/sample_project2/AppConfig.cs
namespace SampleProject2;
/// <summary>
/// Stores configuration settings used by other parts of the application.
/// एप्लीकेशन के अन्य हिस्सों द्वारा उपयोग की जाने वाली कॉन्फ़िगरेशन सेटिंग्स को स्टोर करता है।
/// </summary>
public static class AppConfig
{
    // --- Constants for Configuration ---
    /// <summary>
    /// Simulates a path to a data file (used by DataHandler).
    /// एक डेटा फ़ाइल के पाथ का अनुकरण करता है (DataHandler द्वारा उपयोग किया जाता है)।
    /// </summary>
    public const string DataFilePath = "data/items.json";
    /// <summary>
    /// A processing parameter (used by ItemProcessor).
    /// एक प्रोसेसिंग पैरामीटर (ItemProcessor द्वारा उपयोग किया जाता है)।
    /// </summary>
    public const int ProcessingThreshold = 100;
    /// <summary>
    /// Example setting for logging level.
    /// लॉगिंग स्तर के लिए उदाहरण सेटिंग.
    /// </summary>
    public const string LogLevel = "INFO";
    /// <summary>
    /// Returns the configured path for the data file.
    /// डेटा फ़ाइल के लिए कॉन्फ़िगर किया गया पाथ देता है।
    /// </summary>
    public static string GetDataPath()
    {
        Console.WriteLine($"Config: Providing data file path: {DataFilePath}");
        return DataFilePath;
    }
    /// <summary>
    /// Returns the configured processing threshold.
    /// कॉन्फ़िगर की गई प्रोसेसिंग थ्रेशोल्ड देता है।
    /// </summary>
    public static int GetThreshold()
    {
        Console.WriteLine($"Config: Providing processing threshold: {ProcessingThreshold}");
        return ProcessingThreshold;
    }
}
```
**संबंध और क्रॉस-लिंकिंग**
कॉन्फ़िगरेशन का उपयोग एप्लीकेशन के कई हिस्सों में किया जाता है। यह विशेष रूप से [डेटा हैंडलर (Data Handler)](04_डेटा-हैंडलर-data-handler.md) और [आइटम प्रोसेसर (Item Processor)](05_आइटम-प्रोसेसर-item-processor.md) के लिए महत्वपूर्ण है, जो डेटा के पाथ और प्रोसेसिंग की सीमा का उपयोग करते हैं।  [मुख्य प्रोग्राम (Main Program)](07_मुख्य-प्रोग्राम-main-program.md) में भी, कॉन्फ़िगरेशन सेटिंग्स को लोड और उपयोग किया जाता है।
**निष्कर्ष**
इस अध्याय में, हमने देखा कि कॉन्फ़िगरेशन एप्लीकेशन की सेटिंग्स को प्रबंधित करने के लिए कितना महत्वपूर्ण है। `AppConfig.cs` फ़ाइल इन सेटिंग्स को स्टोर करती है और उन्हें एप्लीकेशन के अन्य हिस्सों को उपलब्ध कराती है। यह एप्लीकेशन को अधिक लचीला और अनुकूलनीय बनाता है।
This concludes our look at this topic.

> Next, we will examine [डेटा हैंडलर (Data Handler)](04_डेटा-हैंडलर-data-handler.md).


---

*Generated by [SourceLens AI](https://github.com/openXFlow/sourceLensAI) using LLM: `gemini` (cloud) - model: `gemini-2.0-flash` | Language Profile: `Python`*